from __future__ import annotations

import math
import re
import typing as t
import uuid
from urllib.parse import quote

if t.TYPE_CHECKING:
    from .map import Map


class ValidationError(ValueError):
    """Validation error.  If a rule converter raises this exception the rule
    does not match the current URL and the next URL is tried.
    """


class BaseConverter:
    """Base class for all converters.

    .. versionchanged:: 2.3
        ``part_isolating`` defaults to ``False`` if ``regex`` contains a ``/``.
    """

    regex = "[^/]+"
    weight = 100
    part_isolating = True

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)

        # If the converter isn't inheriting its regex, disable part_isolating by default
        # if the regex contains a / character.
        if "regex" in cls.__dict__ and "part_isolating" not in cls.__dict__:
            cls.part_isolating = "/" not in cls.regex

    def __init__(self, map: Map, *args: t.Any, **kwargs: t.Any) -> None:
        self.map = map

    def to_python(self, value: str) -> t.Any:
        return value

    def to_url(self, value: t.Any) -> str:
        # safe = https://url.spec.whatwg.org/#url-path-segment-string
        return quote(str(value), safe="!$&'()*+,/:;=@")


class UnicodeConverter(BaseConverter):
    """This converter is the default converter and accepts any string but
    only one path segment.  Thus the string can not include a slash.

    This is the default validator.

    Example::

        Rule('/pages/<page>'),
        Rule('/<string(length=2):lang_code>')

    :param map: the :class:`Map`.
    :param minlength: the minimum length of the string.  Must be greater
                      or equal 1.
    :param maxlength: the maximum length of the string.
    :param length: the exact length of the string.
    """

    def __init__(
        self,
        map: Map,
        minlength: int = 1,
        maxlength: int | None = None,
        length: int | None = None,
    ) -> None:
        super().__init__(map)
        if length is not None:
            length_regex = f"{{{int(length)}}}"
        else:
            if maxlength is None:
                maxlength_value = ""
            else:
                maxlength_value = str(int(maxlength))
            length_regex = f"{{{int(minlength)},{maxlength_value}}}"
        self.regex = f"[^/]{length_regex}"


class AnyConverter(BaseConverter):
    """Matches one of the items provided.  Items can either be Python
    identifiers or strings::

        Rule('/<any(about, help, imprint, class, "foo,bar"):page_name>')

    :param map: the :class:`Map`.
    :param items: this function accepts the possible items as positional
                  arguments.

    .. versionchanged:: 2.2
        Value is validated when building a URL.
    """

    def __init__(self, map: Map, *items: str) -> None:
        super().__init__(map)
        self.items = set(items)
        self.regex = f"(?:{'|'.join([re.escape(x) for x in items])})"

    def to_url(self, value: t.Any) -> str:
        if value in self.items:
            return str(value)

        valid_values = ", ".join(f"'{item}'" for item in sorted(self.items))
        raise ValueError(f"'{value}' is not one of {valid_values}")


class PathConverter(BaseConverter):
    """Like the default :class:`UnicodeConverter`, but it also matches
    slashes.  This is useful for wikis and similar applications::

        Rule('/<path:wikipage>')
        Rule('/<path:wikipage>/edit')

    :param map: the :class:`Map`.
    """

    part_isolating = False
    regex = "[^/].*?"
    weight = 200


class IntegerConverter(BaseConverter):
    """Accepts integer values.

    Only accepts one representation for each value. Negative zero ``-0`` is not
    allowed, it represents the same value as ``0``. Leading zeros are not
    allowed unless ``fixed_digits`` is set.

    :param map: The map this rule is bound to.
    :param fixed_digits: Require a fixed number of digits. For example, ``4``
        will only match values like ``0001``. The negative sign is not counted,
        ``-0004`` is considered 4 digits.
    :param min: The minimum value, inclusive.
    :param max: The maximum value, inclusive.
    :param signed: Allow negative values.

    .. versionchanged:: 3.2
        Negative zero is not allowed. Leading zeros are not allowed unless
        ``fixed_digits`` is set. The negative sign is not counted for
        ``fixed_digits``. ``to_url`` performs validation.

    .. versionchanged:: 0.15
        The ``signed`` parameter was added.
    """

    weight = 50
    regex = r"[0-9]+"

    def __init__(
        self,
        map: Map,
        fixed_digits: int = 0,
        min: int | None = None,
        max: int | None = None,
        signed: bool = False,
    ) -> None:
        super().__init__(map)
        self.min = min
        self.max = max
        self.fixed_digits = fixed_digits
        self.signed = signed

        if signed:
            self.regex = f"-?{self.regex}"

    def to_python(self, value: str) -> t.Any:
        if self.fixed_digits and len(value.removeprefix("-")) != self.fixed_digits:
            raise ValidationError(f"Must be {self.fixed_digits} digits.")

        try:
            value_num = int(value)
        except ValueError as e:  # if > sys.get_int_max_str_digits()
            raise ValidationError() from e

        if value_num == 0:
            if value.startswith("-"):
                raise ValidationError("Negative zero is not allowed.")

            if not self.fixed_digits and len(value) > 1:
                raise ValidationError("Leading zeros are not allowed.")
        else:
            if not self.fixed_digits and value.removeprefix("-").startswith("0"):
                raise ValidationError("Leading zeros are not allowed.")

        if (self.min is not None and value_num < self.min) or (
            self.max is not None and value_num > self.max
        ):
            raise ValidationError("Outside of allowed range.")

        return value_num

    def to_url(self, value: t.Any) -> str:
        value = int(value)

        if not self.signed and value < 0:
            raise ValidationError("Negative values are not allowed.")

        if (self.min is not None and value < self.min) or (
            self.max is not None and value > self.max
        ):
            raise ValidationError("Outside of allowed range.")

        value_str = str(value)

        if self.fixed_digits:
            if len(value_str.removeprefix("-")) > self.fixed_digits:
                raise ValidationError(
                    f"More than {self.fixed_digits} digits are not allowed."
                )

            return value_str.zfill(self.fixed_digits + (value < 0))

        return str(value)


class FloatConverter(BaseConverter):
    """Accepts float values.

    Only accepts one representation for each value, except where the value
    cannot be precisely converted, such as ``0.1``. Must have an integer and
    decimal part, ``4.`` and ``.4`` are not allowed. Negative zero ``-0.0`` is
    distinct from ``0.0``, so it is allowed. Leading zeros in the integer part
    and trailing zeros in the fraction part are not allowed. Values that are too
    small or large to be converted are not allowed.

    Many values are not exactly expressible as a float and will be parsed to the
    nearest expressible value. Therefore, there is not a 1-to-1 unique mapping
    between URLs and parsed values.

    :param map: The map this rule is bound to.
    :param min: The minimum value, inclusive.
    :param max: The maximum value, inclusive.
    :param signed: Allow negative values.

    .. versionchanged:: 3.2
        Leading and trailing zeros are not allowed. Values that are outside the
        representable range (too tiny or large) are not allowed. ``to_url``
        performs validation and does not produce scientific notation.

    .. versionchanged:: 0.15
        The ``signed`` parameter was added.
    """

    weight = 50
    regex = r"[0-9]+\.[0-9]+"

    def __init__(
        self,
        map: Map,
        min: float | None = None,
        max: float | None = None,
        signed: bool = False,
    ) -> None:
        super().__init__(map)
        self.min = min
        self.max = max
        self.signed = signed

        if signed:
            self.regex = f"-?{self.regex}"

    def to_python(self, value: str) -> t.Any:
        value_num: float = float(value)
        # will convert too small to 0.0, too large to inf

        if value_num == 0:  # 0.0 == -0.0 == 0
            if value not in ("0.0", "-0.0"):  # also prevents leading/trailing zeros
                raise ValidationError("Too small.")
        elif math.isinf(value_num):
            raise ValidationError("Too large.")
        else:
            left, _, right = value.partition(".")

            if (len(left) > 1 and left.removeprefix("-").startswith("0")) or (
                len(right) > 1 and right.endswith("0")
            ):
                raise ValidationError("Leading or trailing zeros are not allowed.")

        if (self.min is not None and value_num < self.min) or (
            self.max is not None and value_num > self.max
        ):
            raise ValidationError("Outside of allowed range.")

        return value_num

    def _float_str(self, value: float) -> str:
        """Convert a float to a string that always uses decimal and not
        scientific notation.
        """
        # Use `str(value)` if it doesn't produce scientific notation.
        if "e" not in (value_str := str(value)):
            return value_str

        sig, _, exp_str = value_str.partition("e")
        left, _, right = sig.partition(".")
        exp = int(exp_str)

        # A big number. Expand trailing zeros in the integer part.
        if exp > 0:
            return f"{left}{right}{'0' * (exp - len(right))}.0"
        # A small number. Expand leading zeros in the fraction part.
        else:
            return f"0.{'0' * (abs(exp) - len(left))}{left}{right}"

    def to_url(self, value: t.Any) -> str:
        value = float(value)

        if not math.isfinite(value):
            raise ValidationError("NaN or Infinity are not allowed.")

        if not self.signed and value < 0:
            raise ValidationError("Negative values are not allowed.")

        if (self.min is not None and value < self.min) or (
            self.max is not None and value > self.max
        ):
            raise ValidationError("Outside of allowed range.")

        return self._float_str(value)


class UUIDConverter(BaseConverter):
    """This converter only accepts UUID strings::

        Rule('/object/<uuid:identifier>')

    .. versionadded:: 0.10

    :param map: the :class:`Map`.
    """

    regex = (
        r"[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-"
        r"[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}"
    )

    def to_python(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)

    def to_url(self, value: uuid.UUID) -> str:
        return str(value)


#: the default converter mapping for the map.
DEFAULT_CONVERTERS: t.Mapping[str, type[BaseConverter]] = {
    "default": UnicodeConverter,
    "string": UnicodeConverter,
    "any": AnyConverter,
    "path": PathConverter,
    "int": IntegerConverter,
    "float": FloatConverter,
    "uuid": UUIDConverter,
}
