# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2008 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from os.path import join, dirname, isfile
from mimetypes import guess_type
from werkzeug.wrappers import BaseRequest as Request, BaseResponse as Response
from werkzeug.debug.repr import debug_repr
from werkzeug.debug.tbtools import get_current_traceback
from werkzeug.debug.console import Console


class DebuggedApplication(object):
    """
    Enables debugging support for a given application::

        from werkzeug.debug import DebuggedApplication
        from myapp import app
        app = DebuggedApplication(app, evalex=True)

    The `evalex` keyword argument allows evaluating expressions in a
    traceback's frame context.

    THIS IS A GAPING SECURITY HOLE IF PUBLICLY ACCESSIBLE!
    """

    def __init__(self, app, evalex=False, request_key='werkzeug.request',
                 console_path='/console'):
        self.app = app
        self.evalex = evalex
        self.console = Console()
        self.frames = {}
        self.tracebacks = {}
        self.request_key = request_key
        self.console_path = console_path

    def handle_console(self, request):
        pass

    def debug_application(self, environ, start_response):
        """Run the application and conserve the traceback frames."""
        try:
            app_iter = self.app(environ, start_response)
            for item in app_iter:
                yield item
        except:
            traceback = get_current_traceback()
            for frame in traceback.frames:
                self.frames[frame.id] = frame
            self.tracebacks[traceback.id] = traceback

            try:
                start_response('500 INTERNAL SERVER ERROR', [
                    ('Content-Type', 'text/html; charset=utf-8')
                ])
            except:
                # if we end up here there has been output but an error
                # occurred.  in that situation we can do nothing fancy any
                # more, better log something into the error log and fall
                # back gracefully.
                environ['wsgi.errors'].write(
                    '\nDebugging middlware catched exception in streamed '
                    'reponse a point where response headers were already '
                    'sent.\n')
                traceback.log(environ['wsgi.errors'])
                return

            yield traceback.render_full().encode('utf-8', 'replace')
            traceback.log(environ['wsgi.errors'])

    def execute_command(self, request, command, frame):
        return Response(frame.console.eval(command), mimetype='text/html')

    def get_resource(self, request, filename):
        filename = join(dirname(__file__), 'shared', filename)
        if isfile(filename):
            mimetype = guess_type(filename)[0] or 'application/octet-stream'
            f = file(filename, 'rb')
            try:
                return Response(f.read(), mimetype=mimetype)
            finally:
                f.close()
        return Response('Not Found', status=404)

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = self.debug_application
        if self.evalex and request.path == self.console_path:
            response = self.handle_console(request)
        elif request.path.rstrip('/').endswith('/__debugger__'):
            resource = request.args.get('resource')
            frame = self.frames.get(request.args.get('frame', type=int))
            cmd = request.args.get('cmd')
            if resource is not None:
                response = self.get_resource(request, resource)
            elif self.evalex and cmd is not None and frame is not None:
                response = self.execute_command(request, cmd, frame)
        return response(environ, start_response)
