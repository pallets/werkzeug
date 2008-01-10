# -*- coding: utf-8 -*-
"""
    werkzeug.serving
    ~~~~~~~~~~~~~~~~

    This module wraps the `wsgiref` module so that it reloads code
    automatically. Works with any WSGI application but it won't help in
    non `wsgiref` environments. Use it only for development.

    Usage::

        from werkzeug.serving import run_simple
        from myproject import make_app
        run_simple('localhost', 8080, make_app())

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import socket
import sys
import time
import thread
from werkzeug.utils import _log
from wsgiref.simple_server import ServerHandler, WSGIRequestHandler, \
     WSGIServer
from SocketServer import ThreadingMixIn, ForkingMixIn


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
        _log('info', '%s - - [%s] %s %s\n',
            self.address_string(),
            self.requestline,
            code,
            size
        )

    def log_error(self, format, *args):
        _log('error', 'Error:\n%s', format % args)

    def log_message(self, format, *args):
        _log('info', format, args)


def make_server(host, port, app=None, threaded=False, processes=1):
    """
    Create a new wsgiref server that is either threaded, or forks
    or just processes one request after another.
    """
    if threaded and processes > 1:
        raise ValueError("cannot have a multithreaded and "
                         "multi process server.")
    elif threaded:
        class handler(BaseRequestHandler):
            multithreaded = True
        class server(ThreadingMixIn, WSGIServer):
            pass
    elif processes > 1:
        class handler(BaseRequestHandler):
            multiprocess = True
            max_children = processes - 1
        class server(ForkingMixIn, WSGIServer):
            pass
    else:
        handler = BaseRequestHandler
        server = WSGIServer
    srv = server((host, port), handler)
    srv.set_app(app)
    return srv


def reloader_loop(extra_files):
    """When this function is run from the main thread, it will force other
    threads to exit when any modules currently loaded change.

    :param extra_files: a list of additional files it should watch.
    """
    mtimes = {}
    while True:
        for filename in filter(None, [getattr(module, '__file__', None)
                                      for module in sys.modules.values()] +
                                     extra_files):
            while not os.path.isfile(filename):
                filename = os.path.dirname(filename)
                if not filename:
                    break
            if not filename:
                continue

            if filename[-4:] in ('.pyc', '.pyo'):
                filename = filename[:-1]

            try:
                mtime = os.stat(filename).st_mtime
            except OSError:
                continue

            if filename not in mtimes:
                mtimes[filename] = mtime
                continue
            if mtime > mtimes[filename]:
                sys.exit(3)
        time.sleep(1)


def restart_with_reloader():
    """
    Spawn a new Python interpreter with the same arguments as this one,
    but running the reloader thread.
    """
    while 1:
        print '* Restarting with reloader...'
        args = [sys.executable] + sys.argv
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        new_environ = os.environ.copy()
        new_environ['WERKZEUG_RUN_MAIN'] = 'true'
        exit_code = os.spawnve(os.P_WAIT, sys.executable, args, new_environ)
        if exit_code != 3:
            return exit_code


def run_with_reloader(main_func, extra_watch):
    """
    Run the given function in an independent python interpreter.
    """
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        thread.start_new_thread(main_func, ())
        try:
            reloader_loop(extra_watch)
        except KeyboardInterrupt:
            return
    try:
        sys.exit(restart_with_reloader())
    except KeyboardInterrupt:
        pass


def run_simple(hostname, port, application, use_reloader=False,
               extra_files=None, threaded=False, processes=1):
    """
    Start an application using wsgiref and with an optional reloader.
    """
    def inner():
        srv = make_server(hostname, port, application, threaded,
                          processes)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print '* Running on http://%s:%d/' % (hostname or '0.0.0.0', port)
    if use_reloader:
        # Create and destroy a socket so that any exceptions are raised before we
        # spawn a separate Python interpreter and loose this ability.
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((hostname, port))
        test_socket.close()
        run_with_reloader(inner, extra_files or [])
    else:
        inner()
