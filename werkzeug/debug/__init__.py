# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: (c) 2014 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import uuid
import json
import time
import getpass
import hashlib
import mimetypes
from os.path import join, dirname, basename, isfile
from werkzeug.wrappers import BaseRequest as Request, BaseResponse as Response
from werkzeug.http import parse_cookie
from werkzeug.debug.tbtools import get_current_traceback, render_console_html
from werkzeug.debug.console import Console
from werkzeug.security import gen_salt
from werkzeug._internal import _log
from werkzeug._compat import text_type


# DEPRECATED
#: import this here because it once was documented as being available
#: from this module.  In case there are users left ...
from werkzeug.debug.repr import debug_repr  # noqa


PIN_TIME = 60 * 60 * 8


class _ConsoleFrame(object):

    """Helper class so that we can reuse the frame console code for the
    standalone console.
    """

    def __init__(self, namespace):
        self.console = Console(namespace)
        self.id = 0


def get_pin_and_cookie_name(app):
    """Given an application object this returns a semi-stable 9 digit pin
    code and a random key.  The hope is that this is stable between
    restarts to not make debugging particularly frustrating.  If the pin
    was forcefully disabled this returns `None`.

    Second item in the resulting tuple is the cookie name for remembering.
    """
    pin = os.environ.get('WERKZEUG_DEBUG_PIN')
    rv = None
    num = None

    # Pin was explicitly disabled
    if pin == 'off':
        return None, None

    # Pin was provided explicitly
    if pin is not None and pin.replace('-', '').isdigit():
        # If there are separators in the pin, return it directly
        if '-' in pin:
            rv = pin
        else:
            num = pin

    modname = getattr(app, '__module__',
                      getattr(app.__class__, '__module__'))
    bits = [
        getpass.getuser(),
        str(uuid.getnode()),
        modname,
        getattr(app, '__name__', getattr(app.__class__, '__name__')),
    ]

    mod = sys.modules.get(modname)
    bits.append(getattr(mod, '__file__', None))
    bits.append('cookiesalt')

    h = hashlib.md5()
    for bit in bits:
        if not bit:
            continue
        if isinstance(bit, text_type):
            bit = bit.encode('utf-8')
        h.update(bit)

    if num is None:
        num = ('%09d' % int(h.hexdigest(), 16))[:9]

    cookie_name = '__wzd' + h.hexdigest()[:12]

    # Format the pincode in groups of digits for easier remembering if
    # we don't have a result yet.
    if rv is None:
        for group_size in 5, 4, 3:
            if len(num) % group_size == 0:
                rv = '-'.join(num[x:x + group_size].rjust(group_size, '0')
                              for x in range(0, len(num), group_size))
                break
        else:
            rv = num

    return rv, cookie_name


class DebuggedApplication(object):
    """Enables debugging support for a given application::

        from werkzeug.debug import DebuggedApplication
        from myapp import app
        app = DebuggedApplication(app, evalex=True)

    The `evalex` keyword argument allows evaluating expressions in a
    traceback's frame context.

    .. versionadded:: 0.9
       The `lodgeit_url` parameter was deprecated.

    :param app: the WSGI application to run debugged.
    :param evalex: enable exception evaluation feature (interactive
                   debugging).  This requires a non-forking server.
    :param request_key: The key that points to the request object in ths
                        environment.  This parameter is ignored in current
                        versions.
    :param console_path: the URL for a general purpose console.
    :param console_init_func: the function that is executed before starting
                              the general purpose console.  The return value
                              is used as initial namespace.
    :param show_hidden_frames: by default hidden traceback frames are skipped.
                               You can show them by setting this parameter
                               to `True`.
    :param pin_security: can be used to disable the pin based security system.
    :param pin_logging: enables the logging of the pin system.
    """

    def __init__(self, app, evalex=False, request_key='werkzeug.request',
                 console_path='/console', console_init_func=None,
                 show_hidden_frames=False, lodgeit_url=None,
                 pin_security=True, pin_logging=True):
        if lodgeit_url is not None:
            from warnings import warn
            warn(DeprecationWarning('Werkzeug now pastes into gists.'))
        if not console_init_func:
            console_init_func = None
        self.app = app
        self.evalex = evalex
        self.frames = {}
        self.tracebacks = {}
        self.request_key = request_key
        self.console_path = console_path
        self.console_init_func = console_init_func
        self.show_hidden_frames = show_hidden_frames
        self.secret = gen_salt(20)
        self._failed_pin_auth = 0

        self.pin_logging = pin_logging
        if pin_security:
            # Print out the pin for the debugger on standard out.
            if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' and \
               pin_logging:
                _log('warning', ' * Debugger is active!')
                if self.pin is None:
                    _log('warning', ' * Debugger pin disabled.  '
                         'DEBUGGER UNSECURED!')
                else:
                    _log('info', ' * Debugger pin code: %s' % self.pin)
        else:
            self.pin = None

    def _get_pin(self):
        if not hasattr(self, '_pin'):
            self._pin, self._pin_cookie = get_pin_and_cookie_name(self.app)
        return self._pin

    def _set_pin(self, value):
        self._pin = value

    pin = property(_get_pin, _set_pin)
    del _get_pin, _set_pin

    @property
    def pin_cookie_name(self):
        """The name of the pin cookie."""
        if not hasattr(self, '_pin_cookie'):
            self._pin, self._pin_cookie = get_pin_and_cookie_name(self.app)
        return self._pin_cookie

    def debug_application(self, environ, start_response):
        """Run the application and conserve the traceback frames."""
        app_iter = None
        try:
            app_iter = self.app(environ, start_response)
            for item in app_iter:
                yield item
            if hasattr(app_iter, 'close'):
                app_iter.close()
        except Exception:
            if hasattr(app_iter, 'close'):
                app_iter.close()
            traceback = get_current_traceback(
                skip=1, show_hidden_frames=self.show_hidden_frames,
                ignore_system_exceptions=True)
            for frame in traceback.frames:
                self.frames[frame.id] = frame
            self.tracebacks[traceback.id] = traceback

            try:
                start_response('500 INTERNAL SERVER ERROR', [
                    ('Content-Type', 'text/html; charset=utf-8'),
                    # Disable Chrome's XSS protection, the debug
                    # output can cause false-positives.
                    ('X-XSS-Protection', '0'),
                ])
            except Exception:
                # if we end up here there has been output but an error
                # occurred.  in that situation we can do nothing fancy any
                # more, better log something into the error log and fall
                # back gracefully.
                environ['wsgi.errors'].write(
                    'Debugging middleware caught exception in streamed '
                    'response at a point where response headers were already '
                    'sent.\n')
            else:
                is_trusted = self.is_trusted(environ)
                yield traceback.render_full(evalex=self.evalex,
                                            evalex_trusted=is_trusted,
                                            secret=self.secret) \
                    .encode('utf-8', 'replace')

            traceback.log(environ['wsgi.errors'])

    def execute_command(self, request, command, frame):
        """Execute a command in a console."""
        return Response(frame.console.eval(command), mimetype='text/html')

    def display_console(self, request):
        """Display a standalone shell."""
        if 0 not in self.frames:
            if self.console_init_func is None:
                ns = {}
            else:
                ns = dict(self.console_init_func())
            ns.setdefault('app', self.app)
            self.frames[0] = _ConsoleFrame(ns)
        is_trusted = self.is_trusted(request.environ)
        return Response(render_console_html(secret=self.secret,
                                            evalex_trusted=is_trusted),
                        mimetype='text/html')

    def paste_traceback(self, request, traceback):
        """Paste the traceback and return a JSON response."""
        rv = traceback.paste()
        return Response(json.dumps(rv), mimetype='application/json')

    def get_resource(self, request, filename):
        """Return a static resource from the shared folder."""
        filename = join(dirname(__file__), 'shared', basename(filename))
        if isfile(filename):
            mimetype = mimetypes.guess_type(filename)[0] \
                or 'application/octet-stream'
            f = open(filename, 'rb')
            try:
                return Response(f.read(), mimetype=mimetype)
            finally:
                f.close()
        return Response('Not Found', status=404)

    def is_trusted(self, environ):
        """Checks if the request passed the pin test."""
        if self.pin is None:
            return True
        ts = parse_cookie(environ).get(self.pin_cookie_name, type=int)
        if ts is None:
            return False
        return (time.time() - PIN_TIME) < ts

    def pin_auth(self, request):
        """Authenticates with the pin."""
        exhausted = False
        auth = False
        if self.is_trusted(request.environ):
            auth = True
        elif self._failed_pin_auth > 10:
            exhausted = True
        else:
            entered_pin = request.args.get('pin')
            if entered_pin.strip().replace('-', '') == \
               self.pin.replace('-', ''):
                self._failed_pin_auth = 0
                auth = True
            else:
                time.sleep(self._failed_pin_auth > 5 and 5.0 or 0.5)
                self._failed_pin_auth += 1
                auth = False

        rv = Response(json.dumps({
            'auth': auth,
            'exhausted': exhausted,
        }), mimetype='application/json')
        if auth:
            rv.set_cookie(self.pin_cookie_name, str(int(time.time())),
                          httponly=True)
        return rv

    def log_pin_request(self):
        """Log the pin if needed."""
        if self.pin_logging and self.pin is not None:
            _log('info', ' * To enable the debugger you need to '
                 'enter the security pin:')
            _log('info', ' * Debugger pin code: %s' % self.pin)
        return Response('')

    def __call__(self, environ, start_response):
        """Dispatch the requests."""
        # important: don't ever access a function here that reads the incoming
        # form data!  Otherwise the application won't have access to that data
        # any more!
        request = Request(environ)
        response = self.debug_application
        if request.args.get('__debugger__') == 'yes':
            cmd = request.args.get('cmd')
            arg = request.args.get('f')
            secret = request.args.get('s')
            traceback = self.tracebacks.get(request.args.get('tb', type=int))
            frame = self.frames.get(request.args.get('frm', type=int))
            if cmd == 'resource' and arg:
                response = self.get_resource(request, arg)
            elif cmd == 'paste' and traceback is not None and \
                    secret == self.secret:
                response = self.paste_traceback(request, traceback)
            elif cmd == 'pinauth' and secret == self.secret:
                response = self.pin_auth(request)
            elif cmd == 'printpin' and secret == self.secret:
                response = self.log_pin_request()
            elif self.evalex and cmd is not None and frame is not None \
                    and self.secret == secret and \
                    self.is_trusted(environ):
                response = self.execute_command(request, cmd, frame)
        elif self.evalex and self.console_path is not None and \
                request.path == self.console_path:
            response = self.display_console(request)
        return response(environ, start_response)
