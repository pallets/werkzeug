from __future__ import annotations

import typing as t

from .datastructures import HeaderSet
from .http import dump_header

if t.TYPE_CHECKING:
    import typing_extensions as te

    from werkzeug.sansio.response import Response


class _DSProto(t.Protocol):
    _on_update: t.Callable[[te.Self], None] | None

    @classmethod
    def from_header(cls, value: str | None) -> te.Self: ...

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

    def register_setter(self, fset: t.Callable[[Response, _DS], None]) -> te.Self:
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

        value = self.cls.from_header(obj.headers.get(self.key))
        value._on_update = make_structure_on_update(obj, self.key, self.cls)
        return value

    def __set__(self, obj: Response, value: _DS | None) -> None:
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
