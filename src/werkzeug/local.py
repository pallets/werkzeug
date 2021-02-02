import copy
import math
import operator
import typing as t
import warnings
from functools import partial
from functools import update_wrapper

from .wsgi import ClosingIterator

# Each thread has its own greenlet, use that as the identifier for the
# context. If greenlets are not available fall back to the current
# thread ident.
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    from threading import get_ident

if t.TYPE_CHECKING:
    from wsgiref.types import WSGIApplication


class _CannotUseContextVar(Exception):
    pass


try:
    from contextvars import ContextVar

    # Gevent < 20.5 does not patch contextvars
    try:
        from gevent.monkey import is_object_patched
    except ImportError:
        pass
    else:
        if is_object_patched("threading", "local") and not is_object_patched(
            "contextvars", "ContextVar"
        ):
            raise _CannotUseContextVar()

    # Eventlet does not patch contextvars at all
    try:
        from eventlet.patcher import is_monkey_patched
    except ImportError:
        pass
    else:
        if is_monkey_patched("thread") and not is_monkey_patched("contextvars"):
            raise _CannotUseContextVar()

except (ImportError, _CannotUseContextVar):

    class ContextVar:  # type: ignore
        """A fake ContextVar for Python3.6 based on the ident function."""

        def __init__(self, _name):
            self.ident_func = get_ident
            self.storage = {}

        def get(self, default):
            return self.storage.get(self.ident_func(), default)

        def set(self, value):
            self.storage[self.ident_func()] = value


def release_local(local: t.Union["Local", "LocalStack"]) -> None:
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
    __slots__ = ("_storage", "_ident_func")

    def __init__(self) -> None:
        object.__setattr__(self, "_storage", ContextVar("local_storage"))
        object.__setattr__(self, "_ident_func", get_ident)

    @property
    def __storage__(self):
        warnings.warn(
            "__storage__ is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._storage.get({})

    @property
    def __ident_func__(self):
        if not hasattr(self._storage, "ident_func"):
            raise RuntimeError(
                "The __ident_func__ should not be used in Python 3.7+ "
                "as a ContextVar is used."
            )
        else:
            warnings.warn(
                "__ident_func__ is deprecated and does not work with Python 3.7+",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._ident_func

    @__ident_func__.setter
    def __ident_func__(self, func):
        if not hasattr(self._storage, "ident_func"):
            raise RuntimeError(
                "The __ident_func__ cannot be changed in Python 3.7+ "
                "as a ContextVar is used."
            )
        else:
            warnings.warn(
                "__ident_func__ is deprecated and does not work with Python 3.7+",
                DeprecationWarning,
                stacklevel=2,
            )
            self._ident_func = func

    def __iter__(self) -> t.Iterator[t.Tuple[int, t.Any]]:
        return iter(self._storage.get({}).items())

    def __call__(self, proxy: str) -> "LocalProxy":
        """Create a proxy for a name."""
        return LocalProxy(self, proxy)

    def __release_local__(self) -> None:
        self._storage.set({})

    def __getattr__(self, name: str) -> t.Any:
        values = self._storage.get({})
        try:
            return values[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: t.Any) -> None:
        values = self._storage.get({}).copy()
        values[name] = value
        self._storage.set(values)

    def __delattr__(self, name: str) -> None:
        values = self._storage.get({}).copy()
        try:
            del values[name]
            self._storage.set(values)
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
    def __ident_func__(self) -> t.Callable[[], int]:
        return self._local.__ident_func__

    @__ident_func__.setter
    def __ident_func__(self, value: t.Callable[[], int]) -> None:
        object.__setattr__(self._local, "__ident_func__", value)

    def __call__(self) -> "LocalProxy":
        def _lookup():
            rv = self.top
            if rv is None:
                raise RuntimeError("object unbound")
            return rv

        return LocalProxy(_lookup)

    def push(self, obj: t.Any) -> t.List[t.Any]:
        """Pushes a new item to the stack"""
        rv = getattr(self._local, "stack", None)
        if rv is None:
            self._local.stack = rv = []
        rv.append(obj)
        return rv

    def pop(self) -> t.Any:
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
    def top(self) -> t.Any:
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
        locals: t.Optional[t.Iterable[t.Union[Local, LocalStack]]] = None,
        ident_func: t.Optional[t.Callable[[], int]] = None,
    ) -> None:
        if locals is None:
            self.locals = []
        elif isinstance(locals, Local):
            self.locals = [locals]
        else:
            self.locals = list(locals)
        if ident_func is not None:
            self.ident_func = ident_func
            for local in self.locals:
                object.__setattr__(local, "__ident_func__", ident_func)
        else:
            self.ident_func = get_ident

    def get_ident(self) -> int:
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

    def make_middleware(self, app: "WSGIApplication") -> "WSGIApplication":
        """Wrap a WSGI application so that cleaning up happens after
        request end.
        """

        def application(environ, start_response):
            return ClosingIterator(app(environ, start_response), self.cleanup)

        return application

    def middleware(self, func: "WSGIApplication") -> "WSGIApplication":
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

    def __repr__(self) -> str:
        return f"<{type(self).__name__} storages: {len(self.locals)}>"


class _ProxyLookup:
    """Descriptor that handles proxied attribute lookup for
    :class:`LocalProxy`.

    :param f: The built-in function this attribute is accessed through.
        Instead of looking up the special method, the function call
        is redone on the object.
    :param fallback: Call this method if the proxy is unbound instead of
        raising a :exc:`RuntimeError`.
    :param class_value: Value to return when accessed from the class.
        Used for ``__doc__`` so building docs still works.
    """

    __slots__ = ("bind_f", "fallback", "class_value", "name")

    def __init__(self, f=None, fallback=None, class_value=None):
        if hasattr(f, "__get__"):
            # A Python function, can be turned into a bound method.

            def bind_f(instance, obj):
                return f.__get__(obj, type(obj))

        elif f is not None:
            # A C function, use partial to bind the first argument.

            def bind_f(instance, obj):
                return partial(f, obj)

        else:
            # Use getattr, which will produce a bound method.
            bind_f = None

        self.bind_f = bind_f
        self.fallback = fallback
        self.class_value = class_value

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            if self.class_value is not None:
                return self.class_value

            return self

        try:
            obj = instance._get_current_object()
        except RuntimeError:
            if self.fallback is None:
                raise

            return self.fallback.__get__(instance, owner)

        if self.bind_f is not None:
            return self.bind_f(instance, obj)

        return getattr(obj, self.name)

    def __repr__(self):
        return f"proxy {self.name}"

    def __call__(self, instance, *args, **kwargs):
        """Support calling unbound methods from the class. For example,
        this happens with ``copy.copy``, which does
        ``type(x).__copy__(x)``. ``type(x)`` can't be proxied, so it
        returns the proxy type and descriptor.
        """
        return self.__get__(instance, type(instance))(*args, **kwargs)


class _ProxyIOp(_ProxyLookup):
    """Look up an augmented assignment method on a proxied object. The
    method is wrapped to return the proxy instead of the object.
    """

    __slots__ = ()

    def __init__(self, f=None, fallback=None):
        super().__init__(f, fallback)

        def bind_f(instance, obj):
            def i_op(self, other):
                f(self, other)
                return instance

            return i_op.__get__(obj, type(obj))

        self.bind_f = bind_f


def _l_to_r_op(op):
    """Swap the argument order to turn an l-op into an r-op."""

    def r_op(obj, other):
        return op(other, obj)

    return r_op


class LocalProxy:
    """A proxy to the object bound to a :class:`Local`. All operations
    on the proxy are forwarded to the bound object. If no object is
    bound, a :exc:`RuntimeError` is raised.

    .. code-block:: python

        from werkzeug.local import Local
        l = Local()

        # a proxy to whatever l.user is set to
        user = l("user")

        from werkzeug.local import LocalStack
        _request_stack = LocalStack()

        # a proxy to _request_stack.top
        request = _request_stack()

        # a proxy to the session attribute of the request proxy
        session = LocalProxy(lambda: request.session)

    ``__repr__`` and ``__class__`` are forwarded, so ``repr(x)`` and
    ``isinstance(x, cls)`` will look like the proxied object. Use
    ``issubclass(type(x), LocalProxy)`` to check if an object is a
    proxy.

    .. code-block:: python

        repr(user)  # <User admin>
        isinstance(user, User)  # True
        issubclass(type(user), LocalProxy)  # True

    :param local: The :class:`Local` or callable that provides the
        proxied object.
    :param name: The attribute name to look up on a :class:`Local`. Not
        used if a callable is given.

    .. versionchanged:: 2.0
        Updated proxied attributes and methods to reflect the current
        data model.

    .. versionchanged:: 0.6.1
        The class can be instantiated with a callable.
    """

    __slots__ = ("__local", "__name", "__wrapped__")

    def __init__(
        self,
        local: t.Union["Local", t.Callable[[], t.Any]],
        name: t.Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "_LocalProxy__local", local)
        object.__setattr__(self, "_LocalProxy__name", name)

        if callable(local) and not hasattr(local, "__release_local__"):
            # "local" is a callable that is not an instance of Local or
            # LocalManager: mark it as a wrapped function.
            object.__setattr__(self, "__wrapped__", local)

    def _get_current_object(self) -> t.Any:
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        if not hasattr(self.__local, "__release_local__"):  # type: ignore
            return self.__local()  # type: ignore

        try:
            return getattr(self.__local, self.__name)  # type: ignore
        except AttributeError:
            raise RuntimeError(f"no object bound to {self.__name}")  # type: ignore

    __doc__ = _ProxyLookup(class_value=__doc__)  # type: ignore
    # __del__ should only delete the proxy
    __repr__ = _ProxyLookup(
        repr, fallback=lambda self: f"<{type(self).__name__} unbound>"
    )
    __str__ = _ProxyLookup(str)
    __bytes__ = _ProxyLookup(bytes)
    __format__ = _ProxyLookup()  # type: ignore
    __lt__ = _ProxyLookup(operator.lt)
    __le__ = _ProxyLookup(operator.le)
    __eq__ = _ProxyLookup(operator.eq)
    __ne__ = _ProxyLookup(operator.ne)
    __gt__ = _ProxyLookup(operator.gt)
    __ge__ = _ProxyLookup(operator.ge)
    __hash__ = _ProxyLookup(hash)  # type: ignore
    __bool__ = _ProxyLookup(bool, fallback=lambda self: False)
    __getattr__ = _ProxyLookup(getattr)
    # __getattribute__ triggered through __getattr__
    __setattr__ = _ProxyLookup(setattr)
    __delattr__ = _ProxyLookup(delattr)
    __dir__ = _ProxyLookup(dir, fallback=lambda self: [])  # type: ignore
    # __get__ (proxying descriptor not supported)
    # __set__ (descriptor)
    # __delete__ (descriptor)
    # __set_name__ (descriptor)
    # __objclass__ (descriptor)
    # __slots__ used by proxy itself
    # __dict__ (__getattr__)
    # __weakref__ (__getattr__)
    # __init_subclass__ (proxying metaclass not supported)
    # __prepare__ (metaclass)
    __class__ = _ProxyLookup()  # type: ignore
    __instancecheck__ = _ProxyLookup(lambda self, other: isinstance(other, self))
    __subclasscheck__ = _ProxyLookup(lambda self, other: issubclass(other, self))
    # __class_getitem__ triggered through __getitem__
    __call__ = _ProxyLookup(lambda self, *args, **kwargs: self(*args, **kwargs))
    __len__ = _ProxyLookup(len)
    __length_hint__ = _ProxyLookup(operator.length_hint)
    __getitem__ = _ProxyLookup(operator.getitem)
    __setitem__ = _ProxyLookup(operator.setitem)
    __delitem__ = _ProxyLookup(operator.delitem)
    # __missing__ triggered through __getitem__
    __iter__ = _ProxyLookup(iter)
    __next__ = _ProxyLookup(next)
    __reversed__ = _ProxyLookup(reversed)
    __contains__ = _ProxyLookup(operator.contains)
    __add__ = _ProxyLookup(operator.add)
    __sub__ = _ProxyLookup(operator.sub)
    __mul__ = _ProxyLookup(operator.mul)
    __matmul__ = _ProxyLookup(operator.matmul)
    __truediv__ = _ProxyLookup(operator.truediv)
    __floordiv__ = _ProxyLookup(operator.floordiv)
    __mod__ = _ProxyLookup(operator.mod)
    __divmod__ = _ProxyLookup(divmod)
    __pow__ = _ProxyLookup(pow)
    __lshift__ = _ProxyLookup(operator.lshift)
    __rshift__ = _ProxyLookup(operator.rshift)
    __and__ = _ProxyLookup(operator.and_)
    __xor__ = _ProxyLookup(operator.xor)
    __or__ = _ProxyLookup(operator.or_)
    __radd__ = _ProxyLookup(_l_to_r_op(operator.add))
    __rsub__ = _ProxyLookup(_l_to_r_op(operator.sub))
    __rmul__ = _ProxyLookup(_l_to_r_op(operator.mul))
    __rmatmul__ = _ProxyLookup(_l_to_r_op(operator.matmul))
    __rtruediv__ = _ProxyLookup(_l_to_r_op(operator.truediv))
    __rfloordiv__ = _ProxyLookup(_l_to_r_op(operator.floordiv))
    __rmod__ = _ProxyLookup(_l_to_r_op(operator.mod))
    __rdivmod__ = _ProxyLookup(_l_to_r_op(divmod))
    __rpow__ = _ProxyLookup(_l_to_r_op(pow))
    __rlshift__ = _ProxyLookup(_l_to_r_op(operator.lshift))
    __rrshift__ = _ProxyLookup(_l_to_r_op(operator.rshift))
    __rand__ = _ProxyLookup(_l_to_r_op(operator.and_))
    __rxor__ = _ProxyLookup(_l_to_r_op(operator.xor))
    __ror__ = _ProxyLookup(_l_to_r_op(operator.or_))
    __iadd__ = _ProxyIOp(operator.iadd)
    __isub__ = _ProxyIOp(operator.isub)
    __imul__ = _ProxyIOp(operator.imul)
    __imatmul__ = _ProxyIOp(operator.imatmul)
    __itruediv__ = _ProxyIOp(operator.itruediv)
    __ifloordiv__ = _ProxyIOp(operator.ifloordiv)
    __imod__ = _ProxyIOp(operator.imod)
    __ipow__ = _ProxyIOp(operator.ipow)
    __ilshift__ = _ProxyIOp(operator.ilshift)
    __irshift__ = _ProxyIOp(operator.irshift)
    __iand__ = _ProxyIOp(operator.iand)
    __ixor__ = _ProxyIOp(operator.ixor)
    __ior__ = _ProxyIOp(operator.ior)
    __neg__ = _ProxyLookup(operator.neg)
    __pos__ = _ProxyLookup(operator.pos)
    __abs__ = _ProxyLookup(abs)
    __invert__ = _ProxyLookup(operator.invert)
    __complex__ = _ProxyLookup(complex)
    __int__ = _ProxyLookup(int)
    __float__ = _ProxyLookup(float)
    __index__ = _ProxyLookup(operator.index)
    __round__ = _ProxyLookup(round)
    __trunc__ = _ProxyLookup(math.trunc)
    __floor__ = _ProxyLookup(math.floor)
    __ceil__ = _ProxyLookup(math.ceil)
    __enter__ = _ProxyLookup()
    __exit__ = _ProxyLookup()
    __await__ = _ProxyLookup()
    __aiter__ = _ProxyLookup()
    __anext__ = _ProxyLookup()
    __aenter__ = _ProxyLookup()
    __aexit__ = _ProxyLookup()
    __copy__ = _ProxyLookup(copy.copy)
    __deepcopy__ = _ProxyLookup(copy.deepcopy)
    # __getnewargs_ex__ (pickle through proxy not supported)
    # __getnewargs__ (pickle)
    # __getstate__ (pickle)
    # __setstate__ (pickle)
    # __reduce__ (pickle)
    # __reduce_ex__ (pickle)
