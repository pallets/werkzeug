# -*- coding: utf-8 -*-
"""
    werkzeug.serving
    ~~~~~~~~~~~~~~~~

    There are many ways to serve a WSGI application.  While you're developing
    it you usually don't want a full blown webserver like Apache but a simple
    standalone one.  With Python 2.5 onwards there is the `wsgiref`_ server in
    the standard library.  If you're using older versions of Python you can
    download the package from the cheeseshop.

    However there are some caveats. Sourcecode won't reload itself when
    changed and each time you kill the server using ``^C`` you get an
    `KeyboardInterrupt` error.  While the latter is easy to solve the first
    one can be a pain in the ass in some situations.

    Because of that Werkzeug ships a small wrapper over `wsgiref` that spawns
    the WSGI application in a subprocess and automatically reloads the
    application if a module was changed.

    The easiest way is creating a small ``start-myproject.py`` that runs the
    application::

        #!/usr/bin/env python
        # -*- coding: utf-8 -*-
        from myproject import make_app
        from werkzeug import run_simple

        app = make_app(...)
        run_simple('localhost', 8080, app, use_reloader=True)

    You can also pass it a `extra_files` keyword argument with a list of
    additional files (like configuration files) you want to observe.

    For bigger applications you should consider using `werkzeug.script`
    instead of a simple start file.

    .. _wsgiref: http://cheeseshop.python.org/pypi/wsgiref


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import socket
import sys
import time
import thread
from itertools import chain
try:
    from wsgiref.simple_server import ServerHandler, WSGIRequestHandler, \
         WSGIServer
    have_wsgiref = True
except ImportError:
    have_wsgiref = False
from SocketServer import ThreadingMixIn, ForkingMixIn
from werkzeug._internal import _log


if have_wsgiref:
    class BaseRequestHandler(WSGIRequestHandler):
        """
        Subclass of the normal request handler that thinks it is
        threaded or something like that. The default wsgiref handler
        has wrong information so we need this class.
        """
        multithreaded = False
        multiprocess = False
        _handler_class = None

        def get_handler(self):
            handler = self._handler_class
            if handler is None:
                class handler(ServerHandler):
                    wsgi_multithread = self.multithreaded
                    wsgi_multiprocess = self.multiprocess
                self._handler_class = handler

            rv = handler(self.rfile, self.wfile, self.get_stderr(),
                         self.get_environ())
            rv.request_handler = self
            return rv

        def handle(self):
            self.raw_requestline = self.rfile.readline()
            if self.parse_request():
                self.get_handler().run(self.server.get_app())

        def log_request(self, code='-', size='-'):
            _log('info', '%s -- [%s] %s %s',
                self.address_string(),
                self.requestline,
                code,
                size
            )

        def log_error(self, format, *args):
            _log('error', 'Error: %s', format % args)

        def log_message(self, format, *args):
            _log('info', format, args)


def make_server(host, port, app=None, threaded=False, processes=1,
                request_handler=None):
    """Create a new wsgiref server that is either threaded, or forks
    or just processes one request after another.
    """
    if not have_wsgiref:
        raise RuntimeError('All the Werkzeug serving features require '
                           'an installed wsgiref library.')
    request_handler = request_handler or BaseRequestHandler
    if threaded and processes > 1:
        raise ValueError("cannot have a multithreaded and "
                         "multi process server.")
    elif threaded:
        class request_handler(request_handler):
            multithreaded = True
        class server(ThreadingMixIn, WSGIServer):
            pass
    elif processes > 1:
        class request_handler(request_handler):
            multiprocess = True
        class server(ForkingMixIn, WSGIServer):
            max_children = processes - 1
    else:
        server = WSGIServer
    srv = server((host, port), request_handler)
    srv.set_app(app)
    return srv


def reloader_loop(extra_files=None, interval=1):
    """When this function is run from the main thread, it will force other
    threads to exit when any modules currently loaded change.

    Copyright notice.  This function is based on the autoreload.py from
    the CherryPy trac which originated from WSGIKit which is now dead.

    :param extra_files: a list of additional files it should watch.
    """
    def iter_module_files():
        for module in sys.modules.values():
            filename = getattr(module, '__file__', None)
            if filename:
                while not os.path.isfile(filename):
                    filename = os.path.dirname(filename)
                    if not filename:
                        break
                else:
                    if filename[-4:] in ('.pyc', '.pyo'):
                        filename = filename[:-1]
                    yield filename

    mtimes = {}
    while 1:
        for filename in chain(iter_module_files(), extra_files or ()):
            try:
                mtime = os.stat(filename).st_mtime
            except OSError:
                continue

            old_time = mtimes.get(filename)
            if old_time is None:
                mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                _log('info', ' * Detected change in %r, reloading' % filename)
                sys.exit(3)
        time.sleep(interval)


def restart_with_reloader():
    """Spawn a new Python interpreter with the same arguments as this one,
    but running the reloader thread.
    """
    while 1:
        _log('info', ' * Restarting with reloader...')
        args = [sys.executable] + sys.argv
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        new_environ = os.environ.copy()
        new_environ['WERKZEUG_RUN_MAIN'] = 'true'
        exit_code = os.spawnve(os.P_WAIT, sys.executable, args, new_environ)
        if exit_code != 3:
            return exit_code


def run_with_reloader(main_func, extra_files=None, interval=1):
    """Run the given function in an independent python interpreter."""
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        thread.start_new_thread(main_func, ())
        try:
            reloader_loop(extra_files, interval)
        except KeyboardInterrupt:
            return
    try:
        sys.exit(restart_with_reloader())
    except KeyboardInterrupt:
        pass


def run_simple(hostname, port, application, use_reloader=False,
               use_debugger=False, use_evalex=True,
               extra_files=None, reloader_interval=1, threaded=False,
               processes=1, request_handler=None):
    """Start an application using wsgiref and with an optional reloader.  This
    wraps `wsgiref` to fix the wrong default reporting of the multithreaded
    WSGI variable and adds optional multithreading and fork support.

    :param hostname: The host for the application.  eg: ``'localhost'``
    :param port: The port for the server.  eg: ``8080``
    :param application: the WSGI application to execute
    :param use_reloader: should the server automatically restart the python
                         process if modules were changed?
    :param use_debugger: should the werkzeug debugging system be used?
    :param use_evalex: should the exception evaluation feature be enabled?
    :param extra_files: a list of files the reloader should listen for
                        additionally to the modules.  For example configuration
                        files.
    :param reloader_interval: the interval for the reloader in seconds.
    :param threaded: should the process handle each request in a separate
                     thread?
    :param processes: number of processes to spawn.
    :param request_handler: optional parameter that can be used to replace
                            the default wsgiref request handler.  Have a look
                            at the `werkzeug.serving` sourcecode for more
                            details.
    """
    if use_debugger:
        from werkzeug.debug import DebuggedApplication
        application = DebuggedApplication(application, use_evalex)

    def inner():
        srv = make_server(hostname, port, application, threaded,
                          processes, request_handler)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        display_hostname = hostname or '127.0.0.1'
        _log('info', ' * Running on http://%s:%d/', display_hostname, port)
    if use_reloader:
        # Create and destroy a socket so that any exceptions are raised before
        # we spawn a separate Python interpreter and loose this ability.
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((hostname, port))
        test_socket.close()
        run_with_reloader(inner, extra_files, reloader_interval)
    else:
        inner()
