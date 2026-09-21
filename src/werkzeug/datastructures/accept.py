from __future__ import annotations

import codecs
import collections.abc as cabc
import re
import typing as t

from ..http import dump_options_header
from ..http import parse_list_header
from ..http import parse_options_header

if t.TYPE_CHECKING:
    import typing_extensions as te

_q_value_re = re.compile(r"0(\.[0-9]{,3})?|1(\.0{,3})?")


class Accept(cabc.Sequence[tuple[str, float]]):
    """A parsed ``Accept-Encoding`` header.

    Despite its name, this class is used for the ``Accept-Encoding`` header.
    :class:`.MIMEAccept` is used for the ``Accept`` header.

    .. versionchanged:: 3.2
        Inherits ``Sequence`` instead of ``ImmutableList``.

    .. versionchanged:: 1.0
        Items with equal quality preserve initial order instead of being ordered
        alphabetically.

    .. versionchanged:: 0.5
        Immutability is enforced.
    """

    def __init__(self, values: cabc.Iterable[tuple[str, float]] | None = None) -> None:
        if values is None:
            values = ()

        self._items = tuple(
            sorted(values, key=lambda x: (self._specificity(x[0]), x[1]), reverse=True)
        )

    def _specificity(self, value: str) -> tuple[bool, ...]:
        """Returns a tuple describing the value's specificity."""
        return (value != "*",)

    def _value_matches(self, app_value: str, req_value: str) -> bool:
        """Check if a value matches a specific value in the collection.

        :param app_value: The value to check.
        :param req_value: The value in the collection to check against.
        """
        return req_value == "*" or req_value.lower() == app_value.lower()

    @t.overload
    def __getitem__(self, key: str) -> float: ...
    @t.overload
    def __getitem__(self, key: t.SupportsIndex) -> tuple[str, float]: ...
    @t.overload
    def __getitem__(self, key: slice) -> tuple[tuple[str, float]]: ...
    def __getitem__(
        self, key: str | t.SupportsIndex | slice
    ) -> float | tuple[str, float] | tuple[tuple[str, float]]:
        """Get the quality for the given value, 0 if it is not in the
        collection. Or the entry at the given index, or a slice of entries.
        """
        if isinstance(key, str):
            return self.quality(key)

        return self._items[key]  # type: ignore[return-value]

    def quality(self, value: str) -> float:
        """Get the quality of the first value in the collection that matches the
        given value.

        :param value: The value to match.

        .. versionadded:: 0.6
        """
        for req_value, q in self:
            if self._value_matches(value, req_value):
                return q

        return 0

    def __contains__(self, value: str) -> bool:  # type: ignore[override]
        for req_value, _ in self:
            if self._value_matches(value, req_value):
                return True

        return False

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> cabc.Iterator[tuple[str, float]]:
        return iter(self._items)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        return self._items == other._items

    def __repr__(self) -> str:
        pairs_str = ", ".join(f"({value!r}, {q})" for value, q in self)
        return f"{type(self).__name__}([{pairs_str}])"

    def index(self, value: str | tuple[str, float]) -> int:  # type: ignore[override]
        """Return the index of the first value in the collection that matches
        the given value.

        :param value: A value to match, or a specific ``(value, quality)`` entry.
        :raises ValueError: If the key is not in the collection.

        .. versionchanged:: 0.5
            Raises ``ValueError`` instead of ``IndexError``.
        """
        if (rv := self.find(value)) == -1:
            raise ValueError(value)

        return rv

    def find(self, value: str | tuple[str, float]) -> int:
        """Return the index of the first value in the collection that matches
        the given value, or -1 if not found.

        :param value: A value to match, or a specific ``(value, quality)`` entry.
        """
        if isinstance(value, str):
            for idx, (req_value, _) in enumerate(self):
                if self._value_matches(value, req_value):
                    return idx

            return -1

        return self._items.index(value)

    def values(self) -> cabc.Iterator[str]:
        """Iterate over values, omitting the quality part."""
        for value, _ in self:
            yield value

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a header value and create an instance of this class.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        result = []

        for item in parse_list_header(value):
            item, options = parse_options_header(item)

            if "q" in options:
                # pop q, remaining options are reconstructed
                q_str = options.pop("q").strip(" \t")

                if _q_value_re.fullmatch(q_str) is None:
                    # ignore an invalid q
                    continue

                q = float(q_str)
            else:
                q = 1

            if options:
                # reconstruct the value with remaining options
                item = dump_options_header(item, options)

            result.append((item, q))

        return cls(result)

    def to_header(self) -> str:
        """Convert to a header value."""
        result = []

        for value, q in self:
            if q != 1:
                value = f"{value};q={q}"

            result.append(value)

        return ",".join(result)

    def __str__(self) -> str:
        return self.to_header()

    def _best_single_match(self, app_value: str) -> tuple[str, float] | None:
        for req_value, q in self:
            if self._value_matches(app_value, req_value):
                return req_value, q

        return None

    @t.overload
    def best_match(self, within: cabc.Iterable[str]) -> str | None: ...
    @t.overload
    def best_match(self, within: cabc.Iterable[str], default: str) -> str: ...
    def best_match(
        self, within: cabc.Iterable[str], default: str | None = None
    ) -> str | None:
        """The best value within a list of potential values based on quality
        and specificity. If multiple values have the same score, the first is
        returned.

        :param within: The potential values to pick from.
        :param default: The value to return if there is no match.
        """
        result = default
        best_quality: float = -1
        best_specificity: tuple[float, ...] = (-1,)

        for app_value in within:
            if (match := self._best_single_match(app_value)) is None:
                continue

            req_value, q = match
            specificity = self._specificity(req_value)

            if q <= 0 or q < best_quality:
                continue

            # better quality or same quality but more specific => better match
            if q > best_quality or specificity > best_specificity:
                result = app_value
                best_quality = q
                best_specificity = specificity

        return result

    @property
    def best(self) -> str | None:
        """The best value based on quality and specificity. ``None`` if the
        collection is empty.
        """
        if self:
            return self[0][0]

        return None


_mime_split_re = re.compile(r"/|(?:[ \t]*;[ \t]*)")


def _normalize_mime(value: str) -> list[str]:
    return _mime_split_re.split(value.lower())


class MIMEAccept(Accept):
    """A parsed ``Accept`` header."""

    def _specificity(self, value: str) -> tuple[bool, ...]:
        return tuple(x != "*" for x in _mime_split_re.split(value))

    def _value_matches(self, app_value: str, req_value: str) -> bool:
        # from the client, can't match
        if "/" not in req_value:
            return False

        req_type, req_sub, *req_params = _normalize_mime(req_value)
        req_params.sort()

        # */* is only value that starts with *
        if req_type == "*" and req_sub != "*":
            return False

        # from the application, tell the developer it's not valid
        if "/" not in app_value:
            raise ValueError(f"invalid mimetype {app_value!r}")

        app_type, app_sub, *app_params = _normalize_mime(app_value)
        app_params.sort()

        if app_type == "*" and app_sub != "*":
            raise ValueError(f"invalid mimetype {app_value!r}")

        return (
            (req_type == "*" and req_sub == "*")
            or (app_type == "*" and app_sub == "*")
            or (
                req_type == app_type
                and (
                    req_sub == "*"
                    or app_sub == "*"
                    or (req_sub == app_sub and req_params == app_params)
                )
            )
        )

    @property
    def accept_html(self) -> bool:
        """True if ``text/html`` is accepted, or :attr:`accept_xhtml`."""
        return "text/html" in self or self.accept_xhtml  # type: ignore[comparison-overlap]

    @property
    def accept_xhtml(self) -> bool:
        """True if ``application/xhtml+xml`` or ``application/xml`` is accepted."""
        return "application/xhtml+xml" in self or "application/xml" in self  # type: ignore[comparison-overlap]

    @property
    def accept_json(self) -> bool:
        """True if ``application/json`` is accepted."""
        return "application/json" in self  # type: ignore[comparison-overlap]


_locale_delim_re = re.compile(r"[_-]")


def _normalize_lang(value: str) -> list[str]:
    """Process a language tag for matching."""
    return _locale_delim_re.split(value.lower())


class LanguageAccept(Accept):
    """A parsed ``Accept-Language`` header."""

    def _value_matches(self, app_value: str, req_value: str) -> bool:
        return req_value == "*" or _normalize_lang(app_value) == _normalize_lang(
            req_value
        )

    @t.overload
    def best_match(self, within: cabc.Iterable[str]) -> str | None: ...
    @t.overload
    def best_match(self, within: cabc.Iterable[str], default: str) -> str: ...
    def best_match(
        self, within: cabc.Iterable[str], default: str | None = None
    ) -> str | None:
        """The best value within a list of potential values based on quality
        and specificity. If multiple values have the same score, the first is
        returned.

        Given a list of supported values, finds the best match from
        the list of accepted values.

        If no exact match is found, this will fall back to matching
        the first subtag (primary language only), first with the
        ``Accept`` values, then with the ``within`` values. This is not
        applied to any other language subtags.

        :param within: The potential values to pick from.
        :param default: The value to return if there is no match.
        """
        # Look for an exact match first. If a client accepts "en-US",
        # "en-US" is a valid match at this point.
        if (result := super().best_match(within)) is not None:
            return result

        # Fall back to accepting primary tags. If a client accepts
        # "en-US", "en" is a valid match at this point. Need to use
        # re.split to account for 2 or 3 letter codes.
        fallback = Accept(
            [(_locale_delim_re.split(value, 1)[0], q) for value, q in self]
        )

        if (result := fallback.best_match(within)) is not None:
            return result

        # Fall back to matching primary tags. If the client accepts
        # "en", "en-US" is a valid match at this point.
        fallback_within = [_locale_delim_re.split(value, 1)[0] for value in within]

        # Return a value from the original match list. Find the first
        # original value that starts with the matched primary tag.
        if (result := super().best_match(fallback_within)) is not None:
            return next(item for item in within if item.startswith(result))

        return default


class _CharsetAccept(Accept):
    """A parse ``Accept-Charset`` header."""

    def _value_matches(self, app_value: str, req_value: str) -> bool:
        def _normalize(name: str) -> str:
            try:
                return codecs.lookup(name).name
            except LookupError:
                return name.lower()

        return req_value == "*" or _normalize(app_value) == _normalize(req_value)


if not t.TYPE_CHECKING:

    def __getattr__(name: str) -> t.Any:
        if name == "CharsetAccept":
            import warnings

            warnings.warn(
                "The 'CharsetAccept' class is deprecated and will be removed in"
                " Werkzeug 3.3. The 'Accept-Charset' header is not sent by"
                " browsers, and UTF-8 is assumed.",
                DeprecationWarning,
                stacklevel=2,
            )
            return _CharsetAccept

        raise AttributeError(name)
