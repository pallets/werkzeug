# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2007 by Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import sys
import inspect
import traceback
import code

from werkzeug.debug.render import debug_page, load_resource
from werkzeug.debug.util import ThreadedStream, Namespace, get_uid, \
     get_frame_info
from werkzeug.utils import url_decode


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

    def __init__(self, application, evalex=False):
        self.evalex = bool(evalex)
        self.application = application
        self.tracebacks = {}

    def __call__(self, environ, start_response):
        # exec code in open tracebacks or provide shared data
        if environ.get('PATH_INFO', '').strip('/').endswith('__traceback__'):
            parameters = url_decode(environ.get('QUERY_STRING', ''))
            # shared data
            if 'resource' in parameters and 'mimetype' in parameters:
                data = load_resource(parameters['resource'])
                start_response('200 OK', [
                    ('Content-Type', str(parameters['mimetype'])),
                    ('Content-Length', str(len(data)))
                ])
                yield data
                return
            # execute commands in an existing debug context
            elif self.evalex:
                try:
                    tb = self.tracebacks[parameters['tb']]
                    frame = parameters['frame']
                    context = tb[frame]
                    code = parameters['code']
                except (IndexError, KeyError):
                    pass
                else:
                    result = context.exec_expr(code)
                    start_response('200 OK', [('Content-Type', 'text/plain')])
                    yield result
                    return

        # wrap the application and catch errors.
        appiter = None
        try:
            appiter = self.application(environ, start_response)
            for line in appiter:
                yield line
        except:
            ThreadedStream.install(environ)
            exc_info = sys.exc_info()
            try:
                headers = [('Content-Type', 'text/html; charset=utf-8')]
                start_response('500 INTERNAL SERVER ERROR', headers)
            except:
                pass
            debug_context = self.create_debug_context(environ, exc_info)
            yield debug_page(debug_context).encode('utf-8')

        if hasattr(appiter, 'close'):
            appiter.close()

    def create_debug_context(self, environ, exc_info):
        exception_type, exception_value, tb = exc_info
        # skip first internal frame
        if not tb.tb_next is None:
            tb = tb.tb_next
        plaintb = ''.join(traceback.format_exception(exception_type,
                                                     exception_value, tb))
        # load frames
        frames = []
        frame_map = {}
        tb_uid = None
        if ThreadedStream.can_interact():
            tb_uid = get_uid()
            frame_map = self.tracebacks[tb_uid] = {}

        # walk through frames and collect information
        while tb is not None:
            if not tb.tb_frame.f_locals.get('__traceback_hide__', False):
                if tb_uid:
                    frame_uid = get_uid()
                    frame_map[frame_uid] = InteractiveDebugger(tb.tb_frame)
                else:
                    frame_uid = None
                frame = get_frame_info(tb)
                frame['frame_uid'] = frame_uid
                frames.append(frame)
            tb = tb.tb_next

        # guard for string exceptions
        if isinstance(exception_type, str):
            extypestr = 'string exception'
            exception_value = exception_type
        elif exception_type.__module__ == 'exceptions':
            extypestr = exception_type.__name__
        else:
            extypestr = '%s.%s' % (
                exception_type.__module__,
                exception_type.__name__
            )

        # support for the werkzeug request object or fall back to
        # WSGI environment
        request = environ.get('werkzeug.request')
        if request is not None:
            req_vars = []
            for varname in dir(request):
                if varname[0] == '_':
                    continue
                value = getattr(request, varname)
                if hasattr(value, 'im_func'):
                    continue
                req_vars.append((varname, value))
        else:
            req_vars = [('WSGI Environ', environ)]

        return Namespace(
            evalex =          self.evalex,
            exception_type =  extypestr,
            exception_value = str(exception_value),
            frames =          frames,
            last_frame =      frames[-1],
            plaintb =         plaintb,
            tb_uid =          tb_uid,
            frame_map =       frame_map,
            req_vars =        req_vars,
        )


class InteractiveDebugger(code.InteractiveInterpreter):
    """
    Subclass of the python interactive interpreter that
    automatically captures stdout and buffers older input.
    """

    def __init__(self, frame):
        self.globals = frame.f_globals
        code.InteractiveInterpreter.__init__(self, frame.f_locals)
        self.prompt = '>>> '
        self.buffer = []

    def runsource(self, source):
        prompt = self.prompt
        sys.stdout.push()
        try:
            source_to_eval = ''.join(self.buffer + [source])
            if code.InteractiveInterpreter.runsource(self,
               source_to_eval, '<debugger>', 'single'):
                self.prompt = '... '
                self.buffer.append(source)
            else:
                self.prompt = '>>> '
                del self.buffer[:]
        finally:
            return prompt + source + sys.stdout.release()

    def runcode(self, code):
        try:
            exec code in self.globals, self.locals
        except:
            self.showtraceback()

    def write(self, data):
        sys.stdout.write(data)

    def exec_expr(self, code):
        rv = self.runsource(code)
        if isinstance(rv, unicode):
            return rv.encode('utf-8')
        return rv
