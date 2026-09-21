from __future__ import annotations

import collections.abc as cabc
import typing as t
from datetime import datetime

from .._internal import _plain_int
from ..http import http_date
from ..http import is_byte_range_valid
from ..http import parse_date
from .etag import ETag

if t.TYPE_CHECKING:
    import typing_extensions as te

T = t.TypeVar("T")


class IfRange:
    """A parsed ``If-Range`` header. Either a strong ETag or a datetime, but not
    both. Weak ETag values must not be used.

    :attr:`.Request.if_range` returns an instance.

    :param etag: An unquoted strong ETag value.
    :param date: A timezone-aware datetime.

    .. versionadded:: 0.7
    """

    def __init__(self, etag: str | None = None, date: datetime | None = None):
        self.etag = etag
        """An unquoted strong ETag value."""

        self.date = date
        """A timezone-aware datetime."""

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse an ``If-Range`` header value and create an instance of this
        class. A weak ETag value is discarded.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        if (date := parse_date(value)) is not None:
            return cls(date=date)

        if (etag := ETag.from_header(value)) is None or etag.weak:
            return cls()

        return cls(etag=etag.value)

    def to_header(self) -> str:
        """Convert to an ``If-Range`` header value."""
        if self.date is not None:
            return http_date(self.date)

        if self.etag is not None:
            return ETag(self.etag).to_header()

        return ""

    def __bool__(self) -> bool:
        return self.etag is not None or self.date is not None

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {str(self)!r}>"


class Range:
    """A parsed ``Range`` header.

    :attr:`.Request.range` returns an instance, or ``None`` if the header is not
    set.

    .. versionchanged:: 3.2
        Validation is done in ``from_header``. Values passed to the constructor
        are assumed valid.

    .. versionchanged:: 0.15
        Values passed to the constructor are validated.

    .. versionadded:: 0.7
    """

    def __init__(
        self, units: str, ranges: cabc.Sequence[tuple[int, int | None]]
    ) -> None:
        self.units = units
        """The unit being counted. Only ``"bytes"`` is defined."""

        self.ranges = ranges
        """The parsed ``(start, stop)`` ranges. ``stop`` is exclusive, unlike
        the raw header value. If ``stop`` is ``None``, ``start`` can be positive
        to get the remaining units from that offset, or negative to get that
        number of units from the end.
        """

    def range_for_length(self, length: int | None) -> tuple[int, int] | None:
        """Return the ``(start, stop)`` values to use for a
        :class:`.ContentRange` header with the given complete length. Or ``None``
        if a valid range cannot be constructed.

        This will generate a range regardless of the value of :attr:`units`.
        However, :meth:`.Response.make_conditional` can only handle ``bytes``.

        If there are multiple ranges in the header, this will only return the
        first range.

        :param length: The complete length of the content. ``None`` means the
            value is unknown, and will return ``None``.
        :return: ``(start, stop)`` if the range and length are valid, ``None``
            otherwise.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``make_content_range`` instead.

        .. versionchanged:: 3.2
            Allows units other than ``bytes``. Will return the first range if
            there are multiple.
        """
        import warnings

        warnings.warn(
            "'range_for_length' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'make_content_range` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._private_range_for_length(length)

    def _private_range_for_length(self, length: int | None) -> tuple[int, int] | None:
        if length is None or not self.ranges:
            return None

        start, stop = self.ranges[0]

        if stop is None:
            stop = length

            if start < 0:
                start += length

        if not is_byte_range_valid(start, stop, length):
            return None

        return start, min(stop, length)

    def make_content_range(self, length: int | None) -> ContentRange | None:
        """Create a :class:`.ContentRange` with the given complete length. Or
        ``None`` if a valid range cannot be constructed.

        This will generate a range regardless of the value of :attr:`units`.
        However, :meth:`.Response.make_conditional` can only handle ``bytes``.

        If there are multiple ranges in the header, this will only return the
        first range.

        .. versionchanged:: 3.2
            Allows units other than ``bytes``. Will return the first range if
            there are multiple.
        """
        # TODO inline after deprecation
        if (bounds := self._private_range_for_length(length)) is None:
            return None

        return ContentRange(self.units, bounds[0], bounds[1], length)

    @classmethod
    def from_header(cls, value: str | None) -> te.Self | None:
        """Parse a ``Range`` header value and create an instance of this class,
        or ``None`` if the value is empty.

        .. versionadded:: 3.2
        """
        if not value or "=" not in value:
            return None

        ranges = []
        last_end = 0
        units, _, ranges_str = value.partition("=")
        units = units.strip(" \t").lower()

        for item in ranges_str.split(","):
            item = item.strip(" \t")

            if "-" not in item:
                return None

            if item.startswith("-"):
                if last_end < 0:
                    return None

                try:
                    begin = _plain_int(item)
                except ValueError:
                    return None

                # -0 will parse to 0, and is an invalid suffix length.
                if begin == 0:
                    return None

                end = None
                last_end = -1

            else:
                begin_str, _, end_str = item.partition("-")
                begin_str = begin_str.strip(" \t")
                end_str = end_str.strip(" \t")

                try:
                    begin = _plain_int(begin_str)
                except ValueError:
                    return None

                if begin < last_end or last_end < 0:
                    return None

                if end_str:
                    try:
                        end = _plain_int(end_str) + 1
                    except ValueError:
                        return None

                    if begin >= end:
                        return None
                else:
                    end = None

                last_end = end if end is not None else -1

            ranges.append((begin, end))

        return cls(units, ranges)

    def to_header(self) -> str:
        """Convert to a ``Range`` header value."""
        ranges = []
        for begin, end in self.ranges:
            if end is None:
                ranges.append(f"{begin}-" if begin >= 0 else str(begin))
            else:
                ranges.append(f"{begin}-{end - 1}")
        return f"{self.units}={','.join(ranges)}"

    def to_content_range_header(self, length: int | None) -> str | None:
        """Converts the object into `Content-Range` HTTP header,
        based on given length

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``make_content_range`` then
            call its ``to_header`` method instead.
        """
        import warnings

        warnings.warn(
            "'to_content_range_header' is deprecated and will be removed in"
            " Werkzeug 3.3. Use 'make_content_range` then call its 'to_header'"
            " method instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if (cr := self.make_content_range(length)) is None:
            return None

        return cr.to_header()

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {str(self)!r}>"


class _CallbackProperty(t.Generic[T]):
    def __set_name__(self, owner: type[ContentRange], name: str) -> None:
        self.attr = f"_{name}"

    @t.overload
    def __get__(self, instance: None, owner: None) -> te.Self: ...
    @t.overload
    def __get__(self, instance: ContentRange, owner: type[ContentRange]) -> T: ...
    def __get__(
        self, instance: ContentRange | None, owner: type[ContentRange] | None
    ) -> te.Self | T:
        if instance is None:
            return self

        return instance.__dict__[self.attr]  # type: ignore[no-any-return]

    def __set__(self, instance: ContentRange, value: T) -> None:
        instance.__dict__[self.attr] = value

        if instance._on_update is not None:
            instance._on_update(instance)


class ContentRange:
    """A parsed ``Content-Range`` header.

    Set :attr:`.Response.content_range` to an instance to set the header.
    Modifying the instance will update the header.

    .. versionchanged:: 3.2
        The ``on_update`` parameter was removed. Argument defaults were added.
        Considered false if neither a range nor length is set.

    .. versionadded:: 0.7
    """

    def __init__(
        self,
        units: str = "bytes",
        start: int | None = None,
        stop: int | None = None,
        length: int | None = None,
    ) -> None:
        self._units = units
        self._start = start
        self._stop = stop
        self._length = length
        self._on_update: cabc.Callable[[ContentRange], None] | None = None

    units: str = _CallbackProperty()  # type: ignore[assignment]
    """The unit being counted. Only ``"bytes"`` is defined."""

    start: int | None = _CallbackProperty()  # type: ignore[assignment]
    """The start point, inclusive. ``None`` means the range is unsatisfiable."""

    stop: int | None = _CallbackProperty()  # type: ignore[assignment]
    """The stop point. Exclusive, unlike the raw header value. ``None`` means
    the range is unsatisfiable.
    """

    length: int | None = _CallbackProperty()  # type: ignore[assignment]
    """The complete length of the content. ``None`` means the length is unknown."""

    def set(
        self,
        start: int | None,
        stop: int | None,
        length: int | None = None,
        units: str = "bytes",
    ) -> None:
        """Update the header.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use
            ``request.content_range = ContentRange(...)`` instead.
        """
        import warnings

        warnings.warn(
            "The 'set' method is deprecated and will be removed in Werkzeug 3.3."
            " Use 'request.content_range = ContentRange(...)' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._units = units
        self._start = start
        self._stop = stop
        self._length = length

        if self._on_update is not None:
            self._on_update(self)

    def unset(self) -> None:
        """Unset the header.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``del request.content_range``
            instead.
        """
        import warnings

        warnings.warn(
            "The 'unset' method is deprecated and will be removed in Werkzeug 3.3."
            " Use 'del request.content_range' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.set(None, None, units="")

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a ``Content-Range`` header value and create an instance of this class.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        units, _, range_str = value.partition(" ")
        range_str, sep, length_str = range_str.partition("/")

        if not sep:
            return cls()

        if length_str == "*":
            length = None
        else:
            try:
                length = _plain_int(length_str)
            except ValueError:
                return cls()

            if length < 0:
                return cls()

        if range_str == "*":
            if length_str == "*":
                return cls()

            return cls(units, None, None, length)

        start_str, sep, stop_str = range_str.partition("-")

        if not sep:
            return cls()

        try:
            start = _plain_int(start_str)
            stop = _plain_int(stop_str)
        except ValueError:
            return cls()

        if not (0 <= start <= stop) or (length is not None and length <= stop):
            return cls()

        return cls(units, start, stop + 1, length)

    def to_header(self) -> str:
        """Convert to a ``Content-Range`` header value."""
        if not self:
            return ""

        length = "*" if self._length is None else self._length

        if self._start is None or self._stop is None:
            return f"{self._units} */{length}"

        return f"{self._units} {self._start}-{self._stop - 1}/{length}"

    def __bool__(self) -> bool:
        return not (
            (self._start is None or self._stop is None) and self._length is None
        )

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.to_header()}>"
