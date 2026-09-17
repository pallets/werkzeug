from __future__ import annotations

import collections.abc as cabc
import typing as t
from datetime import datetime

from .._internal import _plain_int
from ..http import http_date
from ..http import is_byte_range_valid
from ..http import parse_date
from ..http import quote_etag
from ..http import unquote_etag

if t.TYPE_CHECKING:
    import typing_extensions as te

T = t.TypeVar("T")


class IfRange:
    """A parsed ``If-Range`` header. Either a strong ETag or a date, but not
    both. Weak ETag values must not be used.

    .. versionadded:: 0.7
    """

    def __init__(self, etag: str | None = None, date: datetime | None = None):
        self.etag = etag
        """A strong ETag value, unquoted, without weakness information. Weak
        ETag values must not be used.
        """

        self.date = date
        """A parsed datetime object."""

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

        value, weak = unquote_etag(value)

        if weak:
            return cls()

        return cls(etag=value)

    def to_header(self) -> str:
        """Convert to an ``If-Range`` header value."""
        if self.date is not None:
            return http_date(self.date)
        if self.etag is not None:
            return quote_etag(self.etag)
        return ""

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {str(self)!r}>"


class Range:
    """Represents a ``Range`` header. All methods only support only
    bytes as the unit. Stores a list of ranges if given, but the methods
    only work if only one range is provided.

    :raise ValueError: If the ranges provided are invalid.

    .. versionchanged:: 0.15
        The ranges passed in are validated.

    .. versionadded:: 0.7
    """

    def __init__(
        self, units: str, ranges: cabc.Sequence[tuple[int, int | None]]
    ) -> None:
        #: The units of this range.  Usually "bytes".
        self.units = units
        #: A list of ``(begin, end)`` tuples for the range header provided.
        #: The ranges are non-inclusive.
        self.ranges = ranges

        for start, end in ranges:
            if start is None or (end is not None and (start < 0 or start >= end)):
                raise ValueError(f"{(start, end)} is not a valid range.")

    def range_for_length(self, length: int | None) -> tuple[int, int] | None:
        """If the range is for bytes, the length is not None and there is
        exactly one range and it is satisfiable it returns a ``(start, stop)``
        tuple, otherwise `None`.
        """
        if self.units != "bytes" or length is None or len(self.ranges) != 1:
            return None
        start, end = self.ranges[0]
        if end is None:
            end = length
            if start < 0:
                start += length
        if is_byte_range_valid(start, end, length):
            return start, min(end, length)
        return None

    def make_content_range(self, length: int | None) -> ContentRange | None:
        """Creates a :class:`~werkzeug.datastructures.ContentRange` object
        from the current range and given content length.
        """
        rng = self.range_for_length(length)
        if rng is not None:
            return ContentRange(self.units, rng[0], rng[1], length)
        return None

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
        """
        range = self.range_for_length(length)
        if range is not None:
            return f"{self.units} {range[0]}-{range[1] - 1}/{length}"
        return None

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
    """The ``Content-Range`` header.

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
        """Simple method to update the ranges."""
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
        """Sets the units to `None` which indicates that the header should
        no longer be used.
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
