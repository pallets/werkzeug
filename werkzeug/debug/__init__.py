# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2007 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import sys
import inspect
import traceback
import code

from werkzeug.debug.render import debug_page, load_resource
from werkzeug.debug.util import ThreadedStream, Namespace, get_uid, \
     get_frame_info, ExceptionRepr
from werkzeug.utils import url_decode


try:
    system_exceptions = (GeneratorExist,)
except NameError:
    system_exceptions = ()
system_exceptions += (SystemExit, KeyboardInterrupt)


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

    def __init__(self, application, evalex=False,
                 request_key='werkzeug.request'):
        self.evalex = bool(evalex)
        self.application = application
        self.request_key = request_key
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
            # pastebin
            elif parameters.get('pastetb'):
                from xmlrpclib import ServerProxy
                try:
                    length = int(environ['CONTENT_LENGTH'])
                except (KeyError, ValueError):
                    length = 0
                data = environ['wsgi.input'].read(length)
                s = ServerProxy('http://paste.pocoo.org/xmlrpc/')
                paste_id = s.pastes.newPaste('pytb', data)
                start_response('200 OK', [('Content-Type', 'text/plain')])
                yield '{"paste_id": %d, "url": "%s"}' % (
                    paste_id,
                    'http://paste.pocoo.org/show/%d' % paste_id
                )
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
        except system_exceptions, e:
            raise e
        except:
            ThreadedStream.install()
            exc_info = sys.exc_info()
            try:
                headers = [('Content-Type', 'text/html; charset=utf-8')]
                start_response('500 INTERNAL SERVER ERROR', headers)
            except:
                pass
            debug_context = self.create_debug_context(environ, exc_info)
            yield debug_page(debug_context)

        if hasattr(appiter, 'close'):
            appiter.close()

    def format_exception(self, exc_info):
        """Format a text/plain traceback."""
        return self.create_debug_context({
            'wsgi.run_once':    True
        }, exc_info, True).plaintb + '\n'

    def create_debug_context(self, environ, exc_info, simple=False):
        exception_type, exception_value, tb = exc_info
        # skip first internal frame
        if not tb.tb_next is None:
            tb = tb.tb_next

        # load frames
        frames = []
        frame_map = {}
        tb_uid = None
        if not environ['wsgi.run_once'] and not environ['wsgi.multiprocess']:
            tb_uid = get_uid()
            frame_map = self.tracebacks[tb_uid] = {}

        plaintb_buffer = ['Traceback (most recent call last):']
        write = plaintb_buffer.append

        # walk through frames and collect information
        while tb is not None:
            if not tb.tb_frame.f_locals.get('__traceback_hide__', False):
                if tb_uid and not simple:
                    frame_uid = get_uid()
                    frame_map[frame_uid] = InteractiveDebugger(self,
                                                               tb.tb_frame)
                else:
                    frame_uid = None
                frame = get_frame_info(tb, simple=simple)
                frame['frame_uid'] = frame_uid
                frames.append(frame)
                write('  File "%s", line %s, in %s' % (
                    frame['filename'],
                    frame['lineno'],
                    frame['function']
                ))
                if frame['raw_context_line'] is None:
                    write('    <no sourcecode available>')
                else:
                    write('    ' + frame['raw_context_line'])
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

        # finialize plain traceback and write it to stderr
        try:
            if isinstance(exception_value, unicode):
                exception_value = exception_value.encode('utf-8')
            else:
                exception_value = str(exception_value)
            exvalstr = ': ' + exception_value
        except:
            exvalstr = ''
        write(extypestr + exvalstr)
        plaintb = '\n'.join(plaintb_buffer)

        if not simple:
            environ['wsgi.errors'].write(plaintb)

        # support for the werkzeug request object or fall back to
        # WSGI environment
        req_vars = []
        if not simple:
            request = environ.get(self.request_key)
            if request is not None:
                for varname in dir(request):
                    if varname.startswith('_'):
                        continue
                    try:
                        value = getattr(request, varname)
                    except Exception, err:
                        value = ExceptionRepr(err)
                    if not hasattr(value, 'im_func'):
                        req_vars.append((varname, value))
            else:
                req_vars.append(('WSGI Environ', environ))

        return Namespace(
            evalex =          self.evalex,
            exception_type =  extypestr,
            exception_value = exception_value,
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

    def __init__(self, middleware, frame):
        self.middleware = middleware
        self.globals = frame.f_globals
        code.InteractiveInterpreter.__init__(self, frame.f_locals)
        self.more = False
        self.buffer = []

    def runsource(self, source):
        if isinstance(source, unicode):
            source = source.encode('utf-8')
        source = source.rstrip() + '\n'
        ThreadedStream.push()
        prompt = self.more and '... ' or '>>> '
        try:
            source_to_eval = ''.join(self.buffer + [source])
            if code.InteractiveInterpreter.runsource(self,
               source_to_eval, '<debugger>', 'single'):
                self.more = True
                self.buffer.append(source)
            else:
                self.more = False
                del self.buffer[:]
        finally:
            return prompt + source + ThreadedStream.fetch()

    def runcode(self, code):
        try:
            exec code in self.globals, self.locals
        except:
            self.write(self.middleware.format_exception(sys.exc_info()))

    def write(self, data):
        sys.stdout.write(data)

    def exec_expr(self, code):
        rv = self.runsource(code)
        if isinstance(rv, unicode):
            return rv.encode('utf-8')
        return rv
