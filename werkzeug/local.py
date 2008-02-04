# -*- coding: utf-8 -*-
"""
    werkzeug.local
    ~~~~~~~~~~~~~~

    Special class to manage request local objects as globals.  This is a
    wrapper around `py.magic.greenlet.getcurrent` if available and
    `threading.currentThread`.

    Use it like this::

        from werkzeug import Local, LocalManager, ClosingIterator

        local = Local()
        local_manager = LocalManager([local])

        def view(request):
            return Response('...')

        def application(environ, start_response):
            request = Request(environ)
            local.request = request
            response = view(request)
            return ClosingIterator(response(environ, start_response),
                                   local_manager.cleanup)

    Additionally you can use the `make_middleware` middleware factory to
    accomplish the same::

        from werkzeug import Local, LocalManager, ClosingIterator

        local = Local()
        local_manager = LocalManager([local])

        def view(request):
            return Response('...')

        def application(environ, start_response):
            request = Request(environ)
            local.request = request
            return view(request)(environ, start_response)

        application = local_manager.make_middleware(application)


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
try:
    from py.magic import greenlet
    get_current_greenlet = greenlet.getcurrent
    del greenlet
except (RuntimeError, ImportError):
    get_current_greenlet = int
try:
    from thread import get_ident as get_current_thread, allocate_lock
except ImportError:
    from dummy_thread import get_ident as get_current_thread, allocate_lock
from werkzeug.utils import ClosingIterator


# get the best ident function.  if greenlets are not installed we can
# savely just use the builtin thread function and save a python methodcall
# and the cost of caculating a hash.
if get_current_greenlet is int:
    get_ident = get_current_thread
else:
    get_ident = lambda: hash((get_current_thread(), get_current_greenlet()))


class Local(object):
    __slots__ = ('__storage__', '__lock__')

    def __init__(self):
        object.__setattr__(self, '__storage__', {})
        object.__setattr__(self, '__lock__', allocate_lock())

    def __iter__(self):
        return self.__storage__.iteritems()

    def __call__(self, proxy):
        """Create a proxy for a name."""
        return LocalProxy(self, proxy)

    def __getattr__(self, name):
        self.__lock__.acquire()
        try:
            try:
                return self.__storage__[get_ident()][name]
            except KeyError:
                raise AttributeError(name)
        finally:
            self.__lock__.release()

    def __setattr__(self, name, value):
        self.__lock__.acquire()
        try:
            ident = get_ident()
            storage = self.__storage__
            if ident in storage:
                storage[ident][name] = value
            else:
                storage[ident] = {name: value}
        finally:
            self.__lock__.release()

    def __delattr__(self, name):
        self.__lock__.acquire()
        try:
            try:
                del self.__storage__[get_ident()][name]
            except KeyError:
                raise AttributeError(name)
        finally:
            self.__lock__.release()


class LocalManager(object):
    """
    Manages local objects.
    """

    def __init__(self, locals=None):
        if locals is None:
            self.locals = []
        else:
            try:
                self.locals = list(locals)
            except TypeError:
                self.locals = [locals]

    def get_ident(self):
        """Returns the current identifier for this context."""
        return get_ident()

    def cleanup(self):
        """
        Call this at the request end to clean up all data stored for
        the current greenlet / thread.
        """
        ident = self.get_ident()
        for local in self.locals:
            local.__storage__.pop(ident, None)

    def make_middleware(self, app):
        """
        Wrap a WSGI application so that cleaning up happens after
        request end.
        """
        def application(environ, start_response):
            return ClosingIterator(app(environ, start_response), self.cleanup)
        return application

    def middleware(self, func):
        """
        Like `make_middleware` but for decorating functions.  Example
        usage::

            @manager.middleware
            def application(environ, start_response):
                ...

        The difference to `make_middleware` is that the function passed
        will have all the arguments copied from the inner application
        (name, docstring, module).
        """
        new_func = self.make_middleware(func)
        try:
            new_func.__name__ = func.__name__
            new_func.__doc__ = func.__doc__
            new_func.__module__ = func.__module__
        except:
            pass
        return new_func

    def __repr__(self):
        return '<%s storages: %d>' % (
            self.__class__.__name__,
            len(self.locals)
        )


class LocalProxy(object):
    """
    Acts as a proxy for a werkzeug local.  Forwards all operations to
    a proxied object.  The only operations not supported for forwarding
    are right handed operands and any kind of assignment.

    Example usage::

        from werkzeug import Local, LocalProxy
        l = Local()
        request = LocalProxy(l, "request")
        user = LocalProxy(l, "user")

    Whenever something is bound to l.user / l.request the proxy objects
    will forward all operations.  If no object is bound a `RuntimeError`
    will be raised.
    """
    __slots__ = ('__local', '__dict__', '__name__')

    def __init__(self, local, name):
        object.__setattr__(self, '_LocalProxy__local', local)
        object.__setattr__(self, '__name__', name)

    def __current_object(self):
        try:
            return getattr(self.__local, self.__name__)
        except AttributeError:
            raise RuntimeError('no object bound to %s' % self.__name__)
    __current_object = property(__current_object)

    def __dict__(self):
        try:
            return self.__current_object.__dict__
        except RuntimeError:
            return AttributeError('__dict__')
    __dict__ = property(__dict__)

    def __repr__(self):
        try:
            obj = self.__current_object
        except RuntimeError:
            return '<%s unbound>' % self.__class__.__name__
        return repr(obj)

    def __nonzero__(self):
        try:
            return bool(self.__current_object)
        except RuntimeError:
            return False

    def __unicode__(self):
        try:
            return unicode(self.__current_oject)
        except RuntimeError:
            return repr(self)

    def __dir__(self):
        try:
            return dir(self.__current_object)
        except RuntimeError:
            return []

    def __getattr__(self, name):
        if name == '__members__':
            return dir(self.__current_object)
        return getattr(self.__current_object, name)

    def __setitem__(self, key, value):
        self.__current_object[key] = value

    def __delitem__(self, key):
        del self.__current_object[key]

    def __setslice__(self, i, j, seq):
        self.__current_object[i:j] = seq

    def __delslice__(self, i, j):
        del self.__current_object[i:j]

    __setattr__ = lambda x, n, v: setattr(x.__current_object, n, v)
    __delattr__ = lambda x, n: delattr(x.__current_object, n)
    __str__ = lambda x: str(x.__current_object)
    __lt__ = lambda x, o: x.__current_object < o
    __le__ = lambda x, o: x.__current_object <= o
    __eq__ = lambda x, o: x.__current_object == o
    __ne__ = lambda x, o: x.__current_object != o
    __gt__ = lambda x, o: x.__current_object > o
    __ge__ = lambda x, o: x.__current_object >= o
    __cmp__ = lambda x, o: cmp(x.__current_object, o)
    __hash__ = lambda x: hash(x.__current_object)
    __call__ = lambda x, *a, **kw: x.__current_object(*a, **kw)
    __len__ = lambda x: len(x.__current_object)
    __getitem__ = lambda x, i: x.__current_object[i]
    __iter__ = lambda x: iter(x.__current_object)
    __contains__ = lambda x, i: i in x.__current_object
    __getslice__ = lambda x, i, j: x.__current_object[i:j]
    __add__ = lambda x, o: x.__current_object + o
    __sub__ = lambda x, o: x.__current_object - o
    __mul__ = lambda x, o: x.__current_object * o
    __floordiv__ = lambda x, o: x.__current_object // o
    __mod__ = lambda x, o: x.__current_object % o
    __divmod__ = lambda x, o: x.__current_object.__divmod__(o)
    __pow__ = lambda x, o: x.__current_object ** o
    __lshift__ = lambda x, o: x.__current_object << o
    __rshift__ = lambda x, o: x.__current_bject >> o
    __and__ = lambda x, o: x.__current_obejct & o
    __xor__ = lambda x, o: x.__current_object ^ o
    __or__ = lambda x, o: x.__current_object | o
    __div__ = lambda x, o: x.__current_object.__div__(o)
    __truediv__ = lambda x, o: x.__current_object.__truediv__(o)
    __neg__ = lambda x: -(x.__current_object)
    __pos__ = lambda x: +(x.__current_object)
    __abs__ = lambda x: abs(x.__current_object)
    __invert__ = lambda x: ~(x.__current_object)
    __complex__ = lambda x: complex(x.__current_object)
    __int__ = lambda x: int(x.__current_object)
    __long__ = lambda x: long(x.__current_object)
    __float__ = lambda x: float(x.__current_object)
    __oct__ = lambda x: oct(x.__current_object)
    __hex__ = lambda x: hex(x.__current_object)
    __index__ = lambda x: x.__current_object.__index__()
    __coerce__ = lambda x, o: x.__coerce__(x, o)
    __enter__ = lambda x: x.__enter__()
    __exit__ = lambda x, *a, **kw: x.__exit__(*a, **kw)
