from __future__ import annotations

import collections.abc as cabc
import typing as t

from ..http import dump_header
from ..http import parse_list_header

if t.TYPE_CHECKING:
    import typing_extensions as te


class HeaderSet(cabc.MutableSet[str]):
    """A parsed set of case-insensitive values from a header. Retains the
    original case and order that values were parsed or added.

    :attr:`.Request.access_control_allow_headers` returns an instance.

    Set :attr:`.Response.vary`, :attr:`.Response.content_language`,
    :attr:`.Response.allow`, :attr:`.Response.access_control_allow_headers`,
    :attr:`.Response.access_control_allow_methods`, and
    :attr:`.Response.access_control_expose_headers` to an instance to set the
    header. Modifying the instance will update the header.

    .. versionchanged:: 3.2
        The ``on_update`` parameter was removed.
    """

    def __init__(self, headers: cabc.Iterable[str] | None = None) -> None:
        self._order = list(headers or ())
        self._lower_set = {x.lower() for x in self._order}
        self._on_update: cabc.Callable[[HeaderSet], None] | None = None

    def add(self, value: str) -> None:
        """Add a value to the set.

        :param value: The value to add.
        """
        self.update((value,))

    def remove(self, value: str) -> None:
        """Remove a value from the set.

        :param value: The value to remove.
        :raises KeyError: If the value is not in the set.

        .. versionchanged:: 0.5
            Raises ``KeyError`` instead of ``IndexError``.
        """
        value_lower = value.lower()

        if value_lower not in self._lower_set:
            raise KeyError(value)

        self._lower_set.remove(value_lower)

        for idx, order_value in enumerate(self._order):
            if order_value.lower() == value_lower:
                del self._order[idx]
                break

        if self._on_update is not None:
            self._on_update(self)

    def update(self, iterable: cabc.Iterable[str]) -> None:
        """Add all values to the set.

        :param iterable: The values to add.
        """
        inserted_any = False

        for value in iterable:
            value_lower = value.lower()

            if value_lower not in self._lower_set:
                self._order.append(value)
                self._lower_set.add(value_lower)
                inserted_any = True

        if inserted_any and self._on_update is not None:
            self._on_update(self)

    def discard(self, value: str) -> None:
        """Remove a value from the set if it is present.

        :param value: The value to remove.
        """
        try:
            self.remove(value)
        except KeyError:
            pass

    def find(self, value: str) -> int:
        """Return the index of the value in the set, or -1 if not found.

        :param value: The value to find.
        """
        value_lower = value.lower()

        for idx, order_value in enumerate(self._order):
            if order_value.lower() == value_lower:
                return idx

        return -1

    def index(self, value: str) -> int:
        """Return the index of the value in the set.

        :param value: The value to find.
        :raises IndexError: If the value is not in the set.
        """
        if (rv := self.find(value)) == -1:
            raise IndexError(value)

        return rv

    def clear(self) -> None:
        """Remove all values from the set."""
        self._lower_set.clear()
        self._order.clear()

        if self._on_update is not None:
            self._on_update(self)

    def as_set(self, preserve_casing: bool = False) -> set[str]:
        """Convert to a plain :class:`set`. Unlike ``set(hs)``, values will be
        lowercase instead of their original case.

        :param preserve_casing: Use the original values instead of the lowercase
            values. Equivalent to ``set(hs)``.
        """
        if preserve_casing:
            return set(self._order)
        return set(self._lower_set)

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a header value and create an instance of this class.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        return cls(parse_list_header(value))

    def to_header(self) -> str:
        """Convert to a header value."""
        return dump_header(self._order)

    def __getitem__(self, idx: t.SupportsIndex) -> str:
        return self._order[idx]

    def __delitem__(self, idx: t.SupportsIndex) -> None:
        value = self._order.pop(idx)
        self._lower_set.remove(value.lower())

        if self._on_update is not None:
            self._on_update(self)

    def __setitem__(self, idx: t.SupportsIndex, value: str) -> None:
        self._lower_set.remove(self._order[idx].lower())
        self._order[idx] = value
        self._lower_set.add(value.lower())

        if self._on_update is not None:
            self._on_update(self)

    def __contains__(self, value: str) -> bool:  # type: ignore[override]
        return value.lower() in self._lower_set

    def __len__(self) -> int:
        return len(self._lower_set)

    def __iter__(self) -> cabc.Iterator[str]:
        return iter(self._order)

    def __bool__(self) -> bool:
        return bool(self._lower_set)

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._order!r})"
