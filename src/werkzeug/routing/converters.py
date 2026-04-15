from __future__ import annotations

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
        than zero.
    :param maxlength: the maximum length of the string.
    :param length: the exact length of the string; this includes the dot in
        the case of the default converter, which uses the pattern
        ``(?P<name>.+)``.
    """

    regex = r"(?P<value>[^/]+)"

    def __init__(
        self,
        map: Map,
        minlength: int | None = None,
        maxlength: int | None = None,
        length: int | None = None,
    ) -> None:
        super().__init__(map)
        if length is not None:
            self.regex = rf"(?P<value>.{{{length}}})"
        if minlength is not None or maxlength is not None:
            self.regex = (
                rf"(?P<value>[^/]{{{minlength or 0},{maxlength or ''}}})"
            )


class AnyConverter(BaseConverter):
    """Matches one of the given values.  This converter is used to match
    either one of the values provided.  The matched value can be referenced
    with the standard name.  Example::

        Rule('/<any(a,b):name>')

    :param map: the :class:`Map`.
    :param values: choices to match.
    """

    regex = r"(?P<value>(?:a|b))"

    def __init__(self, map: Map, *args: str) -> None:
        super().__init__(map)
        self._choices = args

        if args and self.part_isolating:
            self.regex = rf"(?P<value>(?:{'|'.join(args)}))"

    def to_python(self, value: str) -> str:
        if value not in self._choices:
            raise ValidationError()
        return value

    def to_url(self, value: str) -> str:
        if value not in self._choices:
            raise ValidationError()
        return value


class PathConverter(BaseConverter):
    """Matches anything up to a given path segment, optionally including the
    segment itself.

    .. versionchanged:: 2.3
        Added the ``segment`` parameter.

    Example::

        Rule('/<path:top>/<path:last>')

    :param map: the :class:`Map`.
    :param segment: When set to ``True``, the matched value will include the
        path separator in the matched value. Otherwise the path separator is
        not included in the matched value.
    """

    regex = r"(?P<value>.+)"
    part_isolating = False

    def __init__(self, map: Map, segment: bool = False) -> None:
        super().__init__(map)
        if segment:
            self.regex = r"(?P<value>.+)"


class NumberConverter(BaseConverter):
    """Baseclass for `IntegerConverter` and `FloatConverter`.

    :internal:
    """

    weight = 50
    num_convert: t.Callable[[t.Any], t.Any] = int

    def __init__(
        self,
        map: Map,
        fixed_digits: int = 0,
        min: int | None = None,
        max: int | None = None,
        signed: bool = False,
    ) -> None:
        if signed:
            self.regex = self.signed_regex
        super().__init__(map)
        self.fixed_digits = fixed_digits
        self.min = min
        self.max = max
        self.signed = signed

    def to_python(self, value: str) -> t.Any:
        if self.fixed_digits and len(value) != self.fixed_digits:
            raise ValidationError()
        value_num = self.num_convert(value)
        if (self.min is not None and value_num < self.min) or (
            self.max is not None and value_num > self.max
        ):
            raise ValidationError()
        return value_num

    def to_url(self, value: t.Any) -> str:
        value_str = str(self.num_convert(value))
        if self.fixed_digits:
            value_str = value_str.zfill(self.fixed_digits)
        return value_str

    @property
    def signed_regex(self) -> str:
        return f"-?{self.regex}"


class IntegerConverter(NumberConverter):
    """This converter only accepts integer values::

        Rule("/page/<int:page>")

    By default it only accepts unsigned, positive values. The ``signed``
    parameter will enable signed, negative values. ::

        Rule("/page/<int(signed=True):page>")

    :param map: the :class:`Map`.
    :param fixed_digits: The number of fixed digits in the URL. If you
        set this to ``4`` for example, the rule will only match if the
        URL looks like ``/0001/``. The default is variable length.
    :param min: The minimal value.
    :param max: The maximal value.
    :param signed: Allow signed (negative) values.

    .. versionadded:: 0.15
        The ``signed`` parameter.
    """

    regex = r"\d+"


class FloatConverter(NumberConverter):
    """This converter only accepts floating point values::

        Rule("/probability/<float:probability>")

    By default it only accepts unsigned, positive values. The ``signed``
    parameter will enable signed, negative values. ::

        Rule("/offset/<float(signed=True):offset>")

    :param map: The :class:`Map`.
    :param min: The minimal value.
    :param max: The maximal value.
    :param signed: Allow signed (negative) values.

    .. versionadded:: 0.15
        The ``signed`` parameter.
    """

    regex = r"\d+\.\d+"
    num_convert = float

    def __init__(
        self,
        map: Map,
        min: float | None = None,
        max: float | None = None,
        signed: bool = False,
    ) -> None:
        super().__init__(map, min=min, max=max, signed=signed)  # type: ignore

    def to_url(self, value: t.Any) -> str:
        value_float = self.num_convert(value)
        # Use repr to avoid scientific notation for small values.
        # repr(0.00001) -> '1e-05', but formatting with sufficient
        # decimal places produces '0.00001'.
        value_str = f"{value_float:.10f}".rstrip("0").rstrip(".")
        if "." not in value_str:
            value_str += ".0"
        if not self.signed and value_float < 0:
            raise ValidationError()
        return value_str


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