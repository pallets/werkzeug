# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2007 by Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import sys
import cgi
import inspect
import traceback

from werkzeug.debug.render import debug_page
from werkzeug.debug.util import ThreadedStream, get_uid, get_frame_info, Namespace


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
        # exec code in open tracebacks
        if self.evalex and environ.get('PATH_INFO', '').strip('/').endswith('__traceback__'):
            parameters = cgi.parse_qs(environ['QUERY_STRING'])
            try:
                tb = self.tracebacks[parameters['tb'][0]]
                frame = parameters['frame'][0]
                context = tb[frame]
                code = parameters['code'][0].replace('\r','')
            except (IndexError, KeyError):
                pass
            else:
                result = context.exec_expr(code)
                start_response('200 OK', [('Content-Type', 'text/plain')])
                yield result
                return
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
        plaintb = ''.join(traceback.format_exception(*exc_info))

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
                    frame_map[frame_uid] = EvalContext(tb.tb_frame)
                else:
                    frame_uid = None
                frame = get_frame_info(tb)
                frame['frame_uid'] = frame_uid
                frames.append(frame)
            tb = tb.tb_next

        # guard for string exceptions
        if isinstance(exception_type, str):
            extypestr = "string exception"
            exception_value = exception_type
        elif exception_type.__module__ == "exceptions":
            extypestr = exception_type.__name__
        else:
            extypestr = str(exception_type)

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


class EvalContext(object):

    def __init__(self, frm):
        self.locals = frm.f_locals
        self.globals = frm.f_globals

    def exec_expr(self, s):
        sys.stdout.push()
        try:
            try:
                code = compile(s, '<stdin>', 'single', 0, 1)
                exec code in self.globals, self.locals
            except:
                etype, value, tb = sys.exc_info()
                tb = tb.tb_next
                msg = ''.join(traceback.format_exception(etype, value, tb))
                sys.stdout.write(msg)
        finally:
            output = sys.stdout.release()
        return output
