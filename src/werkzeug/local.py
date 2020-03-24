import copy
import math
import operator
from functools import partial
from functools import update_wrapper
from typing import Any
from typing import Callable
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

from .wsgi import ClosingIterator
from werkzeug.types import WSGIEnvironment

if TYPE_CHECKING:
    from werkzeug.debug.console import HTMLStringO, _InteractiveConsole  # noqa: F401

# Each thread has its own greenlet, use that as the identifier for the
# context. If greenlets are not available fall back to the current
# thread ident.
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    from threading import get_ident


def release_local(local: Union["LocalStack", "Local"]) -> None:
    """Releases the contents of the local for the current context.
    This makes it possible to use locals without a manager.

    Example::

        >>> loc = Local()
        >>> loc.foo = 42
        >>> release_local(loc)
        >>> hasattr(loc, 'foo')
        False

    With this function one can release :class:`Local` objects as well
    as :class:`LocalStack` objects.  However it is not possible to
    release data held by proxies that way, one always has to retain
    a reference to the underlying local object in order to be able
    to release it.

    .. versionadded:: 0.6.1
    """
    local.__release_local__()


class Local:
    __slots__ = ("__storage__", "__ident_func__")

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", {})
        object.__setattr__(self, "__ident_func__", get_ident)

    def __iter__(self):
        return iter(self.__storage__.items())

    def __call__(self, proxy: str) -> "LocalProxy":
        """Create a proxy for a name."""
        return LocalProxy(self, proxy)

    def __release_local__(self) -> None:
        self.__storage__.pop(self.__ident_func__(), None)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(
        self, name: str, value: Union["_InteractiveConsole", "HTMLStringO", int]
    ) -> None:
        ident = self.__ident_func__()
        storage = self.__storage__
        try:
            storage[ident][name] = value
        except KeyError:
            storage[ident] = {name: value}

    def __delattr__(self, name: str) -> None:
        try:
            del self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)


class LocalStack:
    """This class works similar to a :class:`Local` but keeps a stack
    of objects instead.  This is best explained with an example::

        >>> ls = LocalStack()
        >>> ls.push(42)
        >>> ls.top
        42
        >>> ls.push(23)
        >>> ls.top
        23
        >>> ls.pop()
        23
        >>> ls.top
        42

    They can be force released by using a :class:`LocalManager` or with
    the :func:`release_local` function but the correct way is to pop the
    item from the stack after using.  When the stack is empty it will
    no longer be bound to the current context (and as such released).

    By calling the stack without arguments it returns a proxy that resolves to
    the topmost item on the stack.

    .. versionadded:: 0.6.1
    """

    def __init__(self) -> None:
        self._local = Local()

    def __release_local__(self) -> None:
        self._local.__release_local__()

    @property
    def __ident_func__(self):
        return self._local.__ident_func__

    @__ident_func__.setter
    def __ident_func__(self, value):
        object.__setattr__(self._local, "__ident_func__", value)

    def __call__(self) -> "LocalProxy":
        def _lookup():
            rv = self.top
            if rv is None:
                raise RuntimeError("object unbound")
            return rv

        return LocalProxy(_lookup)

    def push(self, obj: Any) -> Any:
        """Pushes a new item to the stack"""
        rv = getattr(self._local, "stack", None)
        if rv is None:
            self._local.stack = rv = []  # type: ignore
        rv.append(obj)
        return rv

    def pop(self) -> Any:
        """Removes the topmost item from the stack, will return the
        old value or `None` if the stack was already empty.
        """
        stack = getattr(self._local, "stack", None)
        if stack is None:
            return None
        elif len(stack) == 1:
            release_local(self._local)
            return stack[-1]
        else:
            return stack.pop()

    @property
    def top(self) -> Any:
        """The topmost item on the stack.  If the stack is empty,
        `None` is returned.
        """
        try:
            return self._local.stack[-1]
        except (AttributeError, IndexError):
            return None


class LocalManager:
    """Local objects cannot manage themselves. For that you need a local
    manager.  You can pass a local manager multiple locals or add them later
    by appending them to `manager.locals`.  Every time the manager cleans up,
    it will clean up all the data left in the locals for this context.

    The `ident_func` parameter can be added to override the default ident
    function for the wrapped locals.

    .. versionchanged:: 0.6.1
       Instead of a manager the :func:`release_local` function can be used
       as well.

    .. versionchanged:: 0.7
       `ident_func` was added.
    """

    def __init__(
        self,
        locals: Optional[List[Union[Local, LocalStack]]] = None,
        ident_func: Optional[Callable] = None,
    ) -> None:
        if locals is None:
            self.locals = []
        elif isinstance(locals, Local):
            self.locals = [locals]
        else:
            self.locals = list(locals)  # type: ignore
        if ident_func is not None:
            self.ident_func = ident_func
            for local in self.locals:
                object.__setattr__(local, "__ident_func__", ident_func)
        else:
            self.ident_func = get_ident

    def get_ident(self) -> Any:
        """Return the context identifier the local objects use internally for
        this context.  You cannot override this method to change the behavior
        but use it to link other context local objects (such as SQLAlchemy's
        scoped sessions) to the Werkzeug locals.

        .. versionchanged:: 0.7
           You can pass a different ident function to the local manager that
           will then be propagated to all the locals passed to the
           constructor.
        """
        return self.ident_func()

    def cleanup(self):
        """Manually clean up the data in the locals for this context.  Call
        this at the end of the request or use `make_middleware()`.
        """
        for local in self.locals:
            release_local(local)

    def make_middleware(
        self, app: Callable[[Any, Any], Any]
    ) -> Callable[[WSGIEnvironment, Any], ClosingIterator]:
        """Wrap a WSGI application so that cleaning up happens after
        request end.
        """

        def application(environ, start_response):
            return ClosingIterator(app(environ, start_response), self.cleanup)

        return application

    def middleware(self, func: Callable) -> Callable:
        """Like `make_middleware` but for decorating functions.

        Example usage::

            @manager.middleware
            def application(environ, start_response):
                ...

        The difference to `make_middleware` is that the function passed
        will have all the arguments copied from the inner application
        (name, docstring, module).
        """
        return update_wrapper(self.make_middleware(func), func)

    def __repr__(self):
        return f"<{type(self).__name__} storages: {len(self.locals)}>"


class ProxyAttribute:
    """Descriptor to be used as an attribute on a LocalProxy.

    The `getter` parameter is used to get the attribute from the proxied
    object.  The getter is accessed as though it were defined on the class of
    the proxied object.  Defaults to getting the attribute assigned to the
    same name the descriptor is assigned to.

    The `fallback` parameter can be used to provide default behaviour when
    the current object is not available.  The fallback is accessed as though
    it were defined on the LocalProxy class.  Defaults to raising an attribute
    error, naming the attribute you were trying to access.
    """

    __slots__ = ("getter", "fallback", "name")

    def __init__(self, getter=None, fallback=None):
        self.getter = getter
        self.fallback = fallback

    def __set_name__(self, owner, name):
        self.name = name

    def get_attribute(self, obj):
        if self.getter is None:
            return getattr(obj, self.name)
        try:
            return self.getter.__get__(obj, type(obj))
        except AttributeError:
            return partial(self.getter, obj)

    def get_fallback(self, proxy):
        if self.fallback is None:
            raise AttributeError(self.name)
        return self.fallback.__get__(proxy, type(proxy))

    def __get__(self, instance, owner):
        if instance is None:
            return self

        try:
            current_object = instance._get_current_object()
        except RuntimeError:
            return self.get_fallback(instance)

        return self.get_attribute(current_object)

    def __call__(self, proxy, *args, **kwargs):
        """This descriptor is not intended to be called, but can be accessed
        accidentally in the following manner::

            >>> cls = type(proxy)
            >>> cls.__copy__(proxy)

        In this case, `cls` will end up being `LocalProxy` instead of the class
        of the proxied object, and `cls.__copy__` will end up being this
        descriptor.

        This function proxies that class method call.
        """
        if type(proxy) is not LocalProxy:
            raise TypeError(f"{type(self).__name__!r} object is not callable")

        func = self.__get__(proxy, type(proxy))
        return func(*args, **kwargs)


class ProxyIAttribute(ProxyAttribute):
    def get_attribute(self, obj):
        obj_base_attr = (
            partial(getattr(operator, self.name), obj)
            if self.getter is None
            else super().get_attribute(obj)
        )

        def obj_attr(*args, **kwargs):
            result = obj_base_attr(*args, **kwargs)

            if result is not obj:
                raise TypeError(
                    f"{type(self).__name__!r} does not support augmented assignments "
                    "that do not return `self`"
                )

            return result

        return obj_attr

    def __get__(self, instance, owner):
        if instance is None:
            return self

        obj_attr = super().__get__(instance, owner)

        def proxy_attr(*args, **kwargs):
            obj_attr(*args, **kwargs)
            return instance

        return proxy_attr


class LocalProxy:
    """Acts as a proxy for a werkzeug local.  Forwards all operations to
    a proxied object.

    Augmented assignments
    (+=, -=, *=, @=, /=, //=, %=, **=, <<=, >>=, &=, ^=, |=)
    work only for inplace operations that return self.

    Example usage::

        from werkzeug.local import Local
        l = Local()

        # these are proxies
        request = l('request')
        user = l('user')


        from werkzeug.local import LocalStack
        _response_local = LocalStack()

        # this is a proxy
        response = _response_local()

    Whenever something is bound to l.user / l.request the proxy objects
    will forward all operations.  If no object is bound a :exc:`RuntimeError`
    will be raised.

    To create proxies to :class:`Local` or :class:`LocalStack` objects,
    call the object as shown above.  If you want to have a proxy to an
    object looked up by a function, you can (as of Werkzeug 0.6.1) pass
    a function to the :class:`LocalProxy` constructor::

        session = LocalProxy(lambda: get_current_request().session)

    .. versionchanged:: 0.6.1
       The class can be instantiated with a callable as well now.
    """

    __slots__ = ("__local", "__name__", "__wrapped__")

    def __init__(
        self, local: Union[Any, "LocalProxy", "LocalStack"], name: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "_LocalProxy__local", local)
        object.__setattr__(self, "__name__", name)
        if callable(local) and not hasattr(local, "__release_local__"):
            # "local" is a callable that is not an instance of Local or
            # LocalManager: mark it as a wrapped function.
            object.__setattr__(self, "__wrapped__", local)

    def _get_current_object(self,) -> object:
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        if not hasattr(self.__local, "__release_local__"):
            return self.__local()
        try:
            return getattr(self.__local, self.__name__)
        except AttributeError:
            raise RuntimeError(f"no object bound to {self.__name__}")

    doc = __doc__
    __doc__ = ProxyAttribute(fallback=property(lambda self: self.doc))

    __repr__ = ProxyAttribute(fallback=lambda self: f"<{type(self).__name__} unbound>")
    __str__ = ProxyAttribute()
    __bytes__ = ProxyAttribute()
    __format__ = ProxyAttribute()

    __lt__ = ProxyAttribute()
    __le__ = ProxyAttribute()
    __eq__ = ProxyAttribute()
    __ne__ = ProxyAttribute()
    __gt__ = ProxyAttribute()
    __ge__ = ProxyAttribute()

    __hash__ = ProxyAttribute()

    __bool__ = ProxyAttribute(getter=bool, fallback=lambda self: False)

    __getattr__ = ProxyAttribute(getter=getattr)
    __setattr__ = ProxyAttribute()
    __delattr__ = ProxyAttribute()
    __dir__ = ProxyAttribute(fallback=lambda self: [])

    __get__ = ProxyAttribute()
    __set__ = ProxyAttribute()
    __delete__ = ProxyAttribute()
    __set_name__ = ProxyAttribute()

    __class__ = ProxyAttribute()
    __instancecheck__ = ProxyAttribute()
    __subclasscheck__ = ProxyAttribute()

    __call__ = ProxyAttribute()

    __len__ = ProxyAttribute(getter=len)
    __length_hint__ = ProxyAttribute(getter=operator.length_hint)
    __getitem__ = ProxyAttribute()
    __setitem__ = ProxyAttribute()
    __delitem__ = ProxyAttribute()
    __iter__ = ProxyAttribute()
    __next__ = ProxyAttribute()
    __reversed__ = ProxyAttribute()
    __contains__ = ProxyAttribute()

    __add__ = ProxyAttribute()
    __sub__ = ProxyAttribute()
    __mul__ = ProxyAttribute()
    __matmul__ = ProxyAttribute()
    __truediv__ = ProxyAttribute()
    __floordiv__ = ProxyAttribute(getter=lambda self, other: self // other)
    __mod__ = ProxyAttribute()
    __divmod__ = ProxyAttribute()
    __pow__ = ProxyAttribute()
    __lshift__ = ProxyAttribute()
    __rshift__ = ProxyAttribute()
    __and__ = ProxyAttribute()
    __xor__ = ProxyAttribute()
    __or__ = ProxyAttribute()

    __radd__ = ProxyAttribute(getter=lambda self, other: other + self)
    __rsub__ = ProxyAttribute()
    __rmul__ = ProxyAttribute()
    __rmatmul__ = ProxyAttribute()
    __rtruediv__ = ProxyAttribute(getter=lambda self, other: other / self)
    __rfloordiv__ = ProxyAttribute(getter=lambda self, other: other // self)
    __rmod__ = ProxyAttribute()
    __rdivmod__ = ProxyAttribute()
    __rpow__ = ProxyAttribute()
    __rlshift__ = ProxyAttribute()
    __rrshift__ = ProxyAttribute()
    __rand__ = ProxyAttribute()
    __rxor__ = ProxyAttribute()
    __ror__ = ProxyAttribute()

    __iadd__ = ProxyIAttribute()
    __isub__ = ProxyIAttribute()
    __imul__ = ProxyIAttribute()
    __imatmul__ = ProxyIAttribute()
    __itruediv__ = ProxyIAttribute()
    __ifloordiv__ = ProxyIAttribute()
    __imod__ = ProxyIAttribute()
    __ipow__ = ProxyIAttribute()
    __ilshift__ = ProxyIAttribute()
    __irshift__ = ProxyIAttribute()
    __iand__ = ProxyIAttribute()
    __ixor__ = ProxyIAttribute()
    __ior__ = ProxyIAttribute()

    __neg__ = ProxyAttribute()
    __pos__ = ProxyAttribute()
    __abs__ = ProxyAttribute()
    __invert__ = ProxyAttribute()

    __complex__ = ProxyAttribute(getter=complex)
    __int__ = ProxyAttribute(getter=int)
    __float__ = ProxyAttribute(getter=float)

    __index__ = ProxyAttribute()

    __round__ = ProxyAttribute()
    __trunc__ = ProxyAttribute()
    __floor__ = ProxyAttribute(getter=math.floor)
    __ceil__ = ProxyAttribute(getter=math.ceil)

    __enter__ = ProxyAttribute()
    __exit__ = ProxyAttribute()

    __copy__ = ProxyAttribute(getter=copy.copy)
    __deepcopy__ = ProxyAttribute(getter=copy.deepcopy)
