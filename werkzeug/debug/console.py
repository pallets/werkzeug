# -*- coding: utf-8 -*-
"""
    werkzeug.debug.console
    ~~~~~~~~~~~~~~~~~~~~~~

    Interactive console support.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
import sys
import code
from cgi import escape
from werkzeug.local import Local
from werkzeug.debug.repr import debug_repr


_local = Local()


class HTMLStringO(object):
    """A StringO version that HTML escapes on write."""

    def __init__(self):
        self._buffer = []
        self._write = self._buffer.append

    def reset(self):
        val = ''.join(self._buffer)
        del self._buffer[:]
        return val

    def write(self, x):
        self._write(escape(x))

    def writelines(self, x):
        self._write(escape(''.join(x)))


class ThreadedStream(object):
    """Thread-local wrapper for sys.stdout for the interactive console."""

    def push():
        if sys.stdout is sys.__stdout__:
            sys.stdout = ThreadedStream()
        _local.stream = HTMLStringO()
    push = staticmethod(push)

    def fetch():
        try:
            stream = _local.stream
        except AttributeError:
            return ''
        return stream.reset()
    fetch = staticmethod(fetch)

    def displayhook(obj):
        try:
            stream = _local.stream
        except AttributeError:
            return _displayhook(obj)
        # stream._write bypasses escaping as debug_repr is
        # already generating HTML for us.
        stream._write(debug_repr(obj))
    displayhook = staticmethod(displayhook)

    def __setattr__(self, name, value):
        raise AttributeError('read only attribute %s' % name)

    def __dir__(self):
        return dir(sys.__stdout__)

    def __getattribute__(self, name):
        if name == '__members__':
            return dir(sys.__stdout__)
        try:
            stream = local.stream
        except AttributeError:
            stream = sys.__stdout__
        return getattr(stream, name)

    def __repr__(self):
        return repr(sys.__stdout__)


# add the threaded stream as display hook
_displayhook = sys.displayhook
sys.displayhook = ThreadedStream.displayhook


class _InteractiveConsole(code.InteractiveInterpreter):

    def __init__(self, globals, locals):
        code.InteractiveInterpreter.__init__(self, locals)
        self.globals = globals
        self.more = False
        self.buffer = []

    def runsource(self, source):
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
            from werkzeug.debug.tbtools import get_current_traceback
            self.write(get_current_traceback().render_summary())

    def write(self, data):
        sys.stdout.write(data)

    def exec_expr(self, code):
        rv = self.runsource(code)
        if isinstance(rv, str):
            return rv.decode('utf-8', 'ignore')
        return rv


class Console(object):
    """An interactive console."""

    def __init__(self, globals=None, locals=None):
        if locals is None:
            locals = {}
        if globals is None:
            globals = {}
        self._ipy = _InteractiveConsole(globals, locals)

    def eval(self, code):
        return self._ipy.runsource(code)
