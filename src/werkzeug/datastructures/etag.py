from __future__ import annotations

import collections.abc as cabc
import re
import typing as t

if t.TYPE_CHECKING:
    import typing_extensions as te


class ETag:
    """A parsed ETag value.

    Set :attr:`.Response.etag` to an instance to set the header. Modifying the
    instance will update the header.

    .. versionadded:: 3.2
    """

    _on_update: t.Callable[[ETag], None] | None = None

    def __init__(self, value: str, weak: bool = False) -> None:
        self._value = value
        self._weak = weak

    def _trigger_on_update(self) -> None:
        if self._on_update is not None:
            self._on_update(self)

    @property
    def value(self) -> str:
        """The unquoted value."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self._value = value
        self._trigger_on_update()

    @property
    def weak(self) -> bool:
        """Whether the weak marker is present."""
        return self._weak

    @weak.setter
    def weak(self, value: bool) -> None:
        self._weak = value
        self._trigger_on_update()

    @classmethod
    def from_header(cls, value: str | None) -> te.Self | None:
        """Parse a quoted ETag value and create an instance of this class, or
        ``None`` if the value is empty or invalid.
        """

        if not value:
            return None

        weak = False
        start = 0

        if value.startswith(("W/", "w/")):
            weak = True
            start = 2

        if not (value.startswith('"', start) and value.endswith('"', start)):
            # invalid, value must be quoted
            return None

        return cls(value[start + 1 : -1], weak)

    def to_header(self) -> str:
        if not self.value or '"' in self.value:
            return ""

        if self.weak:
            return f'W/"{self.value}"'

        return f'"{self.value}"'

    def __bool__(self) -> bool:
        return bool(self._value)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, type(self)):
            return NotImplemented

        return self._value == value._value and self._weak == value._weak

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<ETag {self.value!r} {'weak' if self.weak else 'strong'}>"


_etag_re = re.compile(
    r"""
    [ \t]*  # ignore leading space
    ([Ww]/)?  # optional weak marker
    "([^"]*)"  # quoted value
    [ \t]*  # ignore trailing space
    (?:,|\Z)  # only if followed by comma or end
    """,
    flags=re.ASCII | re.VERBOSE,
)


class ETagSet(cabc.Collection[str]):
    """A parsed ``If-Match`` or ``If-None-Match`` header.

    :attr:`.Request.if_match` and :attr:`.Request.if_none_match` return an
    instance.

    :param strong_etags: Unquoted values that were not marked weak.
    :param weak_etags: Unquoted values that were marked weak.
    :param star_tag: Whether ``*`` is present in the header value.

    .. versionchanged:: 3.2
        Renamed from ``ETags``.
    """

    def __init__(
        self,
        strong_etags: cabc.Iterable[str] | None = None,
        weak_etags: cabc.Iterable[str] | None = None,
        star_tag: bool = False,
    ):
        if not star_tag and strong_etags:
            self._strong = frozenset(strong_etags)
        else:
            self._strong = frozenset()

        self._weak = frozenset(weak_etags or ())
        self.star_tag = star_tag

    def as_set(self, include_weak: bool = False) -> set[str]:
        """The values as a :class:`set`. Strong values are always included, weak
        values are optional.

        :param include_weak: Include weak values along with strong values.
        """
        rv = set(self._strong)

        if include_weak:
            rv.update(self._weak)

        return rv

    def is_weak(self, etag: str) -> bool:
        """Check if the given value is in the weak set. Does not check the
        strong set or ``*``.

        :param etag: The unquoted value to check.
        """
        return etag in self._weak

    def is_strong(self, etag: str) -> bool:
        """Check if the given value is in the strong set. Does not check the
        weak set or ``*``.

        :param etag: The unquoted value to check.
        """
        return etag in self._strong

    def contains_weak(self, etag: str) -> bool:
        """Check if the given value is in the strong or weak set. If ``*`` is
        present in the header value, all values are contained.

        :param etag: The unquoted value to check.
        """
        return self.is_weak(etag) or self.contains(etag)

    def contains(self, etag: str) -> bool:
        """Check if the value is in the strong set, ignoring the weak set. If
        ``*`` is present in the header value, all values are contained.

        It is also possible to use the ``in`` operator.

        :param etag: The unquoted value to check.
        """
        if self.star_tag:
            return True

        return self.is_strong(etag)

    def contains_raw(self, etag: str) -> bool:
        """Check if the raw, quoted value is part of the set. Parses the value,
        then calls :meth:`contains_weak` if it is weak, otherwise
        :meth:`contains`.

        :param etag: The raw, quoted value to check.
        """
        if (value := ETag.from_header(etag)) is None:
            return False

        if value.weak:
            return self.contains_weak(value.value)

        return self.contains(value.value)

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a header value and create an instance of this class. Invalid
        items are discarded.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        if value == "*":
            return cls(star_tag=True)

        strong = []
        weak = []
        pos = 0

        while True:
            if (m := _etag_re.match(value, pos)) is None:
                # Skip invalid chars until the next comma or end.
                if (pos := value.find(",", pos) + 1) == 0:
                    break

                continue

            is_weak, tag = m.groups()
            pos = m.end()

            if is_weak:
                weak.append(tag)
            else:
                strong.append(tag)

        return cls(strong, weak)

    def to_header(self) -> str:
        """Convert to a header value."""
        if self.star_tag:
            return "*"

        return ", ".join(
            [f'"{x}"' for x in self._strong] + [f'W/"{x}"' for x in self._weak]
        )

    def __call__(
        self,
        etag: str | None = None,
        data: bytes | None = None,
        include_weak: bool = False,
    ) -> bool:
        """Check if the given unquoted ETag value, or an ETag value generated by
        hashing the given data, is in the set.

        :param etag: The unquoted ETag value to check.
        :param data: The data to generate an ETag value for and check.
        :param include_weak: Use :meth:`contains_weak` instead of
            :meth:`contains`.

        .. versionchanged:: 3.2
            The ``*`` header value is considered.
        """
        if etag is None:
            if data is None:
                raise TypeError("'data' is required when 'etag' is not given.")

            from ..http import generate_etag

            etag = generate_etag(data)

        if include_weak:
            return self.contains_weak(etag)

        return self.contains(etag)

    def __bool__(self) -> bool:
        return bool(self.star_tag or self._strong or self._weak)

    def __str__(self) -> str:
        return self.to_header()

    def __len__(self) -> int:
        return len(self._strong)

    def __iter__(self) -> cabc.Iterator[str]:
        return iter(self._strong)

    def __contains__(self, etag: str) -> bool:  # type: ignore[override]
        return self.contains(etag)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {str(self)!r}>"


if not t.TYPE_CHECKING:

    def __getattr__(name: str) -> t.Any:
        if name == "ETags":
            import warnings

            warnings.warn(
                "'ETags' has been renamed to 'ETagSet'. The old name is deprecated and"
                " will be removed in Werkzeug 3.3.",
                DeprecationWarning,
                stacklevel=2,
            )
            return ETagSet

        raise AttributeError(name)
