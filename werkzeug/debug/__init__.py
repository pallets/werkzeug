# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2008 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from os.path import join, dirname, basename, isfile
from mimetypes import guess_type
from werkzeug.wrappers import BaseRequest as Request, BaseResponse as Response
from werkzeug.debug.repr import debug_repr
from werkzeug.debug.tbtools import get_current_traceback
from werkzeug.debug.console import Console
from werkzeug.debug.utils import render_template


class _ConsoleFrame(object):
    """
    Helper class so that we can reuse the frame console code for the
    standalone console.
    """

    def __init__(self, namespace):
        self.console = Console(namespace)
        self.id = 0


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
                 console_path='/console', console_init_func=dict):
        self.app = app
        self.evalex = evalex
        self.frames = {}
        self.tracebacks = {}
        self.request_key = request_key
        self.console_path = console_path
        self.console_init_func = console_init_func

    def debug_application(self, environ, start_response):
        """Run the application and conserve the traceback frames."""
        try:
            app_iter = self.app(environ, start_response)
            for item in app_iter:
                yield item
        except:
            traceback = get_current_traceback(skip=1)
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

            yield traceback.render_full(evalex=self.evalex) \
                           .encode('utf-8', 'replace')
            traceback.log(environ['wsgi.errors'])

    def execute_command(self, request, command, frame):
        """Execute a command in a console."""
        return Response(frame.console.eval(command), mimetype='text/html')

    def display_console(self, request):
        """Display a standalone shell."""
        if 0 not in self.frames:
            self.frames[0] = _ConsoleFrame(self.console_init_func())
        return Response(render_template('console.html'), mimetype='text/html')

    def paste_traceback(self, request, traceback):
        """Paste the traceback and return a JSON response."""
        paste_id = traceback.paste()
        return Response('{"url": "http://paste.pocoo.org/show/%d/", "id": %d}'
                        % (paste_id, paste_id), mimetype='application/json')

    def get_source(self, request, frame):
        """Render the source viewer."""
        return Response(frame.render_source(), mimetype='text/html')

    def get_resource(self, request, filename):
        """Return a static resource from the shared folder."""
        filename = join(dirname(__file__), 'shared', basename(filename))
        if isfile(filename):
            mimetype = guess_type(filename)[0] or 'application/octet-stream'
            f = file(filename, 'rb')
            try:
                return Response(f.read(), mimetype=mimetype)
            finally:
                f.close()
        return Response('Not Found', status=404)

    def __call__(self, environ, start_response):
        """Dispatch the requests."""
        # important: don't ever access a function here that reads the incoming
        # form data!  Otherwise the application won't have access to that data
        # any more!
        request = Request(environ)
        response = self.debug_application
        if self.evalex and self.console_path is not None and \
           request.path == self.console_path:
            response = self.display_console(request)
        elif request.path.rstrip('/').endswith('/__debugger__'):
            cmd = request.args.get('cmd')
            arg = request.args.get('f')
            traceback = self.tracebacks.get(request.args.get('tb', type=int))
            frame = self.frames.get(request.args.get('frm', type=int))
            if cmd == 'resource' and arg:
                response = self.get_resource(request, arg)
            elif cmd == 'paste' and traceback is not None:
                response = self.paste_traceback(request, traceback)
            elif cmd == 'source' and frame:
                response = self.get_source(request, frame)
            elif self.evalex and cmd is not None and frame is not None:
                response = self.execute_command(request, cmd, frame)
        return response(environ, start_response)
