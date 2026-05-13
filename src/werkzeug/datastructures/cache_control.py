from __future__ import annotations

import collections.abc as cabc
import typing as t
from inspect import cleandoc

from .._internal import _plain_int
from ..http import dump_header
from ..http import parse_dict_header

if t.TYPE_CHECKING:
    import typing_extensions as te


def _deprecated_cache_control_property(
    key: str,
    empty: t.Any,
    type: type[t.Any] | None,
    *,
    doc: str | None = None,
) -> t.Any:
    """Create a property for a ``Cache-Control`` directive.

    :param key: The directive name.
    :param empty: The value when the directive is present without a value.
    :param convert: The type to convert the value to. A ``ValueError`` returns ``None``.
    :param doc: The docstring for the property. If not given, it is generated
        based on the other params.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 3.3. Use indexing ``cc[key]`` for unknown
        directives.

    .. versionchanged:: 3.1
        Added the ``doc`` parameter.

    .. versionchanged:: 2.0
        Renamed from ``cache_property``.
    """
    import warnings

    warnings.warn(
        "The 'cache_property' and 'cache_control_property' functions are"
        " deprecated and will be removed in Werkzeug 3.3. Use indexing"
        " 'cc[key]' for unknown directives.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _cache_control_property(key, type, empty=empty, mutable=True, doc=doc)


def _cache_control_property(
    key: str,
    convert: type[t.Any] | None = None,
    *,
    empty: t.Any = None,
    mutable: bool = False,
    doc: str | None = None,
) -> t.Any:
    """Create a property for a ``Cache-Control`` directive.

    :meta private:

    :param key: The directive name.
    :param empty: The value when the directive is present without a value.
    :param convert: The type to convert the value to. A ``ValueError`` returns ``None``.
    :param doc: The docstring for the property. If not given, it is generated
        based on the other params.
    :param mutable: Whether the property has a setter and a deleter.
    """
    if doc is None:
        parts = [f"The ``{key}`` directive."]

        if convert is bool:
            parts.append("A ``bool``, ``True`` if present, ``False`` if not.")
        else:
            if convert is None:
                parts.append("A ``str``,")
            else:
                parts.append(f"A ``{convert.__name__}``,")

            if empty is not None:
                parts.append(f"or ``{empty!r}`` if present with no value,")

            parts.append("or ``None`` if not present.")

        doc = " ".join(parts)

    doc = cleandoc(doc)
    get_convert = _plain_int if convert is int else convert

    if not mutable:
        return property(lambda x: x._get_directive(key, empty, get_convert), doc=doc)

    return property(
        lambda x: x._get_directive(key, empty, get_convert),
        lambda x, v: x._set_directive(key, v, convert),
        lambda x: x._del_directive(key),
        doc=doc,
    )


class _CacheControl(cabc.Mapping[str, str | None]):
    _data: cabc.Mapping[str, str | None]

    def __getitem__(self, key: str, /) -> str | None:
        return self._data[key]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> cabc.Iterator[str]:
        return iter(self._data)

    def _get_directive(
        self, key: str, empty: t.Any, convert: t.Callable[[str], t.Any] | None
    ) -> t.Any:
        if convert is bool:
            return key in self

        if key not in self:
            return None

        if (value := self[key]) is None:
            return empty

        if convert is None:
            return value

        try:
            return convert(value)
        except ValueError:
            return None

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a ``Cache-Control`` header value and create an instance of this class.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        return cls(parse_dict_header(value))  # type: ignore[call-arg]

    def to_header(self) -> str:
        """Convert to a ``Cache-Control`` header value."""
        return dump_header(self._data)

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        kv_str = " ".join(f"{k}={v!r}" for k, v in sorted(self._data.items()))
        return f"<{type(self).__name__} {kv_str}>"

    cache_property = staticmethod(_deprecated_cache_control_property)


class RequestCacheControl(_CacheControl):
    """The ``Cache-Control`` request header. This is immutable, values received
    in the request cannot be modified.

    Typically, you'll access the various directive properties. It also allows
    indexing `cc[directive]` to access unknown directives that do not have
    corresponding properties.

    :param values: Values parsed from the request header.

    .. versionchanged:: 3.2
        Inherits ``Mapping`` instead of ``ImmutableDict``.

        The ``on_update`` parameter was removed.

        The ``cache_property`` method is deprecated and will be removed in
        Werkzeug 3.3. Use indexing ``cc[key]`` for unknown directives.

    .. versionchanged:: 3.1
        Dict values are always ``str | None``. Setting properties will
        convert the value to a string. Setting a non-bool property to
        ``False`` is equivalent to setting it to ``None``. Getting typed
        properties will return ``None`` if conversion raises
        ``ValueError``, rather than the string.

       ``max_age`` is ``None`` if present without a value, rather
       than ``-1``.

        ``no_cache`` is a boolean, it is ``True`` instead of ``"*"``
        when present.

        ``max_stale`` is ``True`` if present without a value, rather
        than ``"*"``.

       ``no_transform`` is a boolean. Previously it was mistakenly
       always ``None``.

       ``min_fresh`` is ``None`` if present without a value, rather
       than ``"*"``.

    .. versionchanged:: 2.1
        Setting int properties such as ``max_age`` will convert the
        value to an int.

    .. versionadded:: 0.5
        Response-only properties are not present on this request class.
    """

    def __init__(
        self,
        values: cabc.Mapping[str, str | None]
        | cabc.Iterable[tuple[str, str | None]]
        | None = None,
    ) -> None:
        if values is None:
            values = {}
        elif not isinstance(values, cabc.Mapping):
            import warnings

            warnings.warn(
                "Passing an iterable instead of a mapping is deprecated and"
                " will be removed in Werkzeug 3.3.",
                DeprecationWarning,
                stacklevel=2,
            )
            values = dict(values)

        self._data = values

    max_age = _cache_control_property("max-age", int)
    max_stale: int | t.Literal[True] | None = _cache_control_property(
        "max-stale", int, empty=True
    )
    min_fresh: int | None = _cache_control_property("min-fresh", int)
    no_cache: bool = _cache_control_property("no-cache", bool)
    no_store: bool = _cache_control_property("no-store", bool)
    no_transform: bool = _cache_control_property("no-transform", bool)
    only_if_cached: bool = _cache_control_property("only-if-cached", bool)
    stale_if_error: int | None = _cache_control_property("stale-if-error", int)


class ResponseCacheControl(cabc.MutableMapping[str, str | None], _CacheControl):
    """The ``Cache-Control`` response header. This is mutable to allow updating
    the response before sending.

    Typically, you'll use the various directive properties. It also allows
    indexing `cc[directive]` to get, set, or delete unknown directives that do
    not have corresponding properties.

    :param values: Initial values to set.

    .. versionchanged:: 3.2
        Inherits ``MutableMapping`` instead of ``dict``.

        The ``on_update`` parameter was removed.

        The ``cache_property`` method is deprecated and will be removed in
        Werkzeug 3.3. Use indexing ``cc[key]`` for unknown directives.

    .. versionchanged:: 3.1
        Dict values are always ``str | None``. Setting properties will
        convert the value to a string. Setting a non-bool property to
        ``False`` is equivalent to setting it to ``None``. Getting typed
        properties will return ``None`` if conversion raises
        ``ValueError``, rather than the string.

        ``no_cache`` is ``True`` if present without a value, rather than
        ``"*"``.

        ``private`` is ``True`` if present without a value, rather than
        ``"*"``.

       ``no_transform`` is a boolean. Previously it was mistakenly
       always ``None``.

        Added the ``must_understand``, ``stale_while_revalidate``, and
        ``stale_if_error`` properties.

    .. versionchanged:: 2.1.1
        ``s_maxage`` converts the value to an int.

    .. versionchanged:: 2.1
        Setting int properties such as ``max_age`` will convert the
        value to an int.

    .. versionadded:: 0.5
       Request-only properties are not present on this response class.

    .. versionchanged:: 0.4
       Setting ``no_cache`` or ``private`` to ``True`` will set the
       implicit value ``"*"``.
    """

    _data: cabc.MutableMapping[str, str | None]

    def __init__(
        self,
        values: cabc.Mapping[str, str | None]
        | cabc.Iterable[tuple[str, str | None]]
        | None = None,
    ) -> None:
        if values is None:
            values = {}
        elif isinstance(values, cabc.Mapping):
            if not isinstance(values, cabc.MutableMapping):
                values = dict(values)
        else:
            import warnings

            warnings.warn(
                "Passing an iterable instead of a mapping is deprecated and"
                " will be removed in Werkzeug 3.3.",
                DeprecationWarning,
                stacklevel=2,
            )
            values = dict(values)

        self._data = values
        self._on_update: t.Callable[[ResponseCacheControl], None] | None = None

    def _trigger_on_update(self) -> None:
        if self._on_update is not None:
            self._on_update(self)

    def __setitem__(self, key: str, value: str | None, /) -> None:
        self._data[key] = value
        self._trigger_on_update()

    def __delitem__(self, key: str, /) -> None:
        del self._data[key]
        self._trigger_on_update()

    def _set_directive(
        self, key: str, value: t.Any, convert: type[t.Any] | None
    ) -> None:
        if convert is bool:
            if value:
                self._data[key] = None
            else:
                self._data.pop(key, None)
        elif value is None or value is False:
            self._data.pop(key, None)
        elif value is True:
            self._data[key] = None
        else:
            if convert is not None:
                value = convert(value)

            self._data[key] = str(value)

        self._trigger_on_update()

    def _del_directive(self, key: str) -> None:
        self._data.pop(key, None)
        self._trigger_on_update()

    max_age: int | None = _cache_control_property("max-age", int, mutable=True)
    s_maxage: int | None = _cache_control_property("s-maxage", int, mutable=True)
    # https://httpwg.org/specs/rfc9111.html#cache-response-directive.no-cache
    # This can be with or without a value, not mentioned on MDN.
    no_cache: str | t.Literal[True] | None = _cache_control_property(
        "no-cache", str, empty=True, mutable=True
    )
    no_store: bool = _cache_control_property("no-store", bool, mutable=True)
    no_transform: bool = _cache_control_property("no-transform", bool, mutable=True)
    must_revalidate: bool = _cache_control_property(
        "must-revalidate", bool, mutable=True
    )
    proxy_revalidate: bool = _cache_control_property(
        "proxy-revalidate", bool, mutable=True
    )
    must_understand: bool = _cache_control_property(
        "must-understand", bool, mutable=True
    )
    # https://httpwg.org/specs/rfc9111.html#cache-response-directive.private
    # This can be with or without a value, not mentioned on MDN.
    private: str | t.Literal[True] | None = _cache_control_property(
        "private", str, empty=True, mutable=True
    )
    public: bool = _cache_control_property("public", bool, mutable=True)
    immutable: bool = _cache_control_property("immutable", bool, mutable=True)
    stale_while_revalidate: int | None = _cache_control_property(
        "stale-while-revalidate", int, mutable=True
    )
    stale_if_error: int | None = _cache_control_property(
        "stale-if-error", int, mutable=True
    )


if not t.TYPE_CHECKING:

    def __getattr__(name: str) -> t.Any:
        if name == "cache_control_property":
            import warnings

            warnings.warn(
                "The 'cache_control_property' function is deprecated and will"
                " be removed in Werkzeug 3.3. Use indexing 'cc[key]' for"
                " unknown directives.",
                DeprecationWarning,
                stacklevel=2,
            )
            return _deprecated_cache_control_property

        raise AttributeError(name)
