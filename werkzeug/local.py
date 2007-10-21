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

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
try:
    from py.magic import greenlet
    get_current_greenlet = greenlet.getcurrent
    del greenlet
except ImportError:
    get_current_greenlet = lambda: None
try:
    from thread import get_ident as get_current_thread
    from threading import Lock
except ImportError:
    from dummy_thread import get_ident as get_current_thread
    from dummy_threading import Lock


def get_ident():
    """
    Return a unique number for the current greenlet in the current thread.
    """
    return hash((get_current_thread(), get_current_greenlet()))


class Local(object):

    def __init__(self):
        self.__dict__.update(
            __storage={},
            __lock=Lock()
        )

    def __getattr__(self, name):
        self.__dict__['__lock'].acquire()
        try:
            ident = get_ident()
            if ident not in self.__dict__['__storage']:
                raise AttributeError(name)
            try:
                return self.__dict__['__storage'][ident][name]
            except KeyError:
                raise AttributeError(name)
        finally:
            self.__dict__['__lock'].release()

    def __setattr__(self, name, value):
        self.__dict__['__lock'].acquire()
        try:
            ident = get_ident()
            storage = self.__dict__['__storage']
            if ident in storage:
                storage[ident][name] = value
            else:
                storage[ident] = {name: value}
        finally:
            self.__dict__['__lock'].release()

    def __delattr__(self, name):
        self.__dict__['__lock'].acquire()
        try:
            ident = get_ident()
            if ident not in self.__dict__['__storage']:
                raise AttributeError(name)
            try:
                del self.__dict__['__storage'][ident][name]
            except KeyError:
                raise AttributeError(name)
        finally:
            self.__dict__['__lock'].release()


class LocalManager(objects):
    """
    Manages local objects.
    """

    def __init__(self, locals=None):
        self.locals = locals and list(locals) or []

    def cleanup(self):
        """
        Call this at the request end to clean up all data stored for
        the current greenlet / thread.
        """
        ident = get_ident()
        for local in self.locals:
            local.__lock.acquire()
            try:
                local.__storage.pop(ident, None)
            finally:
                local.__lock.release()

    def __repr__(self):
        return '<%s storages: %d>' % (
            self.__class__.__name__,
            len(self.locals)
        )
