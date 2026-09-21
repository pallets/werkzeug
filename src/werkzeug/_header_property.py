from __future__ import annotations

import typing as t

from .datastructures.set import HeaderSet
from .http import dump_header

if t.TYPE_CHECKING:
    import typing_extensions as te

    from .sansio.response import Response

T = t.TypeVar("T")


class environ_property(t.Generic[T]):
    """A property that returns a key from :attr:`.Request.environ`.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 3.3. Access ``environ`` directly instead.
    """

    def __init__(
        self,
        name: str,
        default: T | None = None,
        load_func: t.Callable[[str], T] | None = None,
        dump_func: t.Callable[[T], str] = str,
        read_only: bool = True,
        doc: str | None = None,
    ) -> None:
        self.name = name
        self.default = default
        self.load_func = load_func
        self.dump_func = dump_func
        self.read_only = read_only

        if doc is not None:
            self.__doc__ = doc

    @t.overload
    def __get__(self, obj: None, cls: type[t.Any], /) -> te.Self: ...
    @t.overload
    def __get__(self, obj: t.Any, cls: type[t.Any] | None = ..., /) -> T: ...
    def __get__(
        self, obj: t.Any | None = None, cls: type[t.Any] | None = None, /
    ) -> T | te.Self:
        if obj is None:
            return self

        try:
            value: t.Any = obj.environ[self.name]
        except KeyError:
            value = self.default

        if self.load_func is not None:
            try:
                value = self.load_func(value)
            except (ValueError, TypeError):
                value = self.default

        return value  # type: ignore[no-any-return]

    def __set__(self, obj: t.Any, value: T) -> None:
        if self.read_only:
            raise AttributeError("read only property")

        obj.environ[self.name] = self.dump_func(value)

    def __delete__(self, obj: t.Any) -> None:
        if self.read_only:
            raise AttributeError("read only property")

        obj.environ.pop(self.name, None)

    def __repr__(self) -> str:
        return f"<environ_property {self.name}>"


class header_property(t.Generic[T]):
    """A property that returns a key from ``headers``.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 3.3. Access ``headers`` directly instead.
    """

    def __init__(
        self,
        name: str,
        default: T | None = None,
        load_func: t.Callable[[str], T] | None = None,
        dump_func: t.Callable[[T | t.Any], str | None] = str,
        read_only: bool = False,
        doc: str | None = None,
    ) -> None:
        self.name = name
        self.default = default
        self.load_func = load_func
        self.dump_func = dump_func
        self.read_only = read_only

        if doc is not None:
            self.__doc__ = doc

    @t.overload
    def __get__(self, obj: None, cls: type[t.Any], /) -> te.Self: ...
    @t.overload
    def __get__(self, obj: t.Any, cls: type[t.Any] | None = ..., /) -> T: ...
    def __get__(
        self, obj: t.Any | None = None, cls: type[t.Any] | None = None, /
    ) -> T | te.Self:
        if obj is None:
            return self

        try:
            value: t.Any = obj.headers[self.name]
        except KeyError:
            value = self.default

        if self.load_func is not None:
            try:
                value = self.load_func(value)
            except (ValueError, TypeError):
                value = self.default

        if self.read_only:
            # Cache to avoid repeated calls.
            obj.__dict__[self.name] = value

        return value  # type: ignore[no-any-return]

    def __set__(self, obj: t.Any, value: T | t.Any | None) -> None:
        if self.read_only:
            raise AttributeError("read only property")

        if value is None:
            del obj.headers[self.name]
            return

        result = self.dump_func(value)

        if not result:
            del obj.headers[self.name]
            return

        obj.headers[self.name] = result

    def __delete__(self, obj: t.Any) -> None:
        if self.read_only:
            # Clear the cache.
            obj.__dict__.pop(self.name, None)
        else:
            del obj.headers[self.name]

    def __repr__(self) -> str:
        return f"<header_property {self.name}>"


class _DSProto(t.Protocol):
    _on_update: t.Callable[[te.Self], None] | None

    @classmethod
    def from_header(cls, value: str | None) -> te.Self | None: ...

    def to_header(self) -> str: ...


_DS = t.TypeVar("_DS", bound=_DSProto)


class structure_property(t.Generic[_DS]):
    """A header property that uses a structured header class from
    ``werkzeug.datastructures``. Uses the ``from_header`` classmethod on get,
    and the ``to_header`` method on set. When getting or setting, the instance's
    ``_on_update`` callback is set so that modifying it updates the header.
    Deleting, setting to ``None`` or empty, or modifying to empty all unset the
    header.

    ``HeaderSet`` is special cased to automatically support setting to a
    collection (``set``, ``list``, ``tuple``).

    This is only needed for ``Response``. ``header_property`` is sufficient for
    ``Request`` since it doesn't need to set up ``on_update`` or assignment.

    :param key: The header key.
    :param cls: The structured header class.
    :param doc: The documentation about the header.
    :param deprecate_str: Whether to show a deprecation warning on setting
        ``str``. Otherwise, setting ``str`` is not allowed.
    """

    def __init__(
        self, key: str, cls: type[_DS], doc: str, deprecate_str: bool = False
    ) -> None:
        self.key = key
        self.cls = cls
        self.__doc__ = doc
        self.fset: t.Callable[[Response, t.Any], None] | None = None
        self.deprecate_str = deprecate_str

        if cls is HeaderSet:
            self.fset = make_set_header_set(key)

    def register_setter(self, fset: t.Callable[[Response, t.Any], None]) -> te.Self:
        """Use this setter function instead of the built-in behavior. This will
        only be triggered if the value is not ``None`` or false. It must handle
        setting ``headers`` and ``_on_update``.
        """
        self.fset = fset
        return self

    def __repr__(self) -> str:
        return f"<{self.key} header>"

    @t.overload
    def __get__(self, obj: None, cls: type[Response], /) -> te.Self: ...
    @t.overload
    def __get__(self, obj: t.Any, cls: type[Response] | None = ..., /) -> _DS: ...
    def __get__(
        self, obj: Response | None, owner: type[Response] | None = None, /
    ) -> _DS | te.Self:
        if obj is None:
            return self

        if (value := self.cls.from_header(obj.headers.get(self.key))) is None:
            return None  # type: ignore[return-value]

        value._on_update = make_structure_on_update(obj, self.key, self.cls)
        return value

    def __set__(self, obj: Response, value: _DS | t.Any | None) -> None:
        if not value:
            del obj.headers[self.key]
        elif self.deprecate_str and isinstance(value, str):
            import warnings

            warnings.warn(
                f"Setting '{self.key.lower().replace('-', '_')}' to a string is"
                " deprecated and will not be supported in Werkzeug 3.3. Set a"
                f" '{self.cls.__name__}' instance, or set the string in 'headers'"
                " instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            obj.headers[self.key] = value
        elif self.fset is not None:
            self.fset(obj, value)
        else:
            obj.headers[self.key] = value.to_header()
            value._on_update = make_structure_on_update(obj, self.key, self.cls)

    def __delete__(self, obj: Response) -> None:
        del obj.headers[self.key]


def make_set_header_set(
    key: str,
) -> t.Callable[[Response, HeaderSet | t.Collection[str]], None]:
    """Allow setting ``HeaderSet`` to a collection (``set``, ``list``, ``tuple``).

    :param key: The header key.
    """

    def set_header_set(
        response: Response, value: HeaderSet | t.Collection[str]
    ) -> None:
        if isinstance(value, HeaderSet):
            response.headers[key] = value.to_header()
        else:
            response.headers[key] = dump_header(value)

    return set_header_set


def make_structure_on_update(
    response: Response, key: str, cls: type[_DS]
) -> t.Callable[[_DS], None]:
    """Factory for ``on_update`` functions.

    :param response: The response instance to set the header on.
    :param key: The header key.
    :param cls: The structured header class. Used for type annotation.
    """

    def on_update(value: _DS) -> None:
        if not value:
            del response.headers[key]
        else:
            response.headers[key] = value.to_header()

    return on_update
