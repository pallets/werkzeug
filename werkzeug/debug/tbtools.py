# -*- coding: utf-8 -*-
"""
    werkzeug.debug.tbtools
    ~~~~~~~~~~~~~~~~~~~~~~

    This module provides various traceback related utility functions.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
import re
import os
import sys
import inspect
import traceback
import codecs
from werkzeug.utils import cached_property
from werkzeug.debug.console import Console
from werkzeug.debug.utils import render_template

_coding_re = re.compile(r'coding[:=]\s*([-\w.]+)')
_line_re = re.compile(r'^(.*?)$(?m)')
_funcdef_re = re.compile(r'^(\s*def\s)|(.*(?<!\w)lambda(:|\s))|^(\s*@)')
UTF8_COOKIE = '\xef\xbb\xbf'

system_exceptions = (SystemExit, KeyboardInterrupt)
try:
    system_exceptions += (GeneratorExit,)
except NameError:
    pass


def get_current_traceback(ignore_system_exceptions=False, skip=0):
    """
    Get the current exception info as `Traceback` object.  Per default calling
    this method will reraise system exceptions such as generator exit, system
    exit or others.  This behavior can be disabled by passing `False` to the
    function as first parameter.
    """
    exc_type, exc_value, tb = sys.exc_info()
    if exc_type in system_exceptions:
        raise
    for x in xrange(skip):
        tb = tb.tb_next
    return Traceback(exc_type, exc_value, tb)


class Line(object):
    """Helper for the source renderer."""
    __slots__ = ('lineno', 'code', 'in_frame', 'current')

    def __init__(self, lineno, code):
        self.lineno = lineno
        self.code = code
        self.in_frame = False
        self.current = False

    def classes(self):
        rv = ['line']
        if self.in_frame:
            rv.append('in-frame')
        if self.current:
            rv.append('current')
        return rv
    classes = property(classes)


class Traceback(object):
    """Wraps a traceback."""

    def __init__(self, exc_type, exc_value, tb):
        self.exc_type = exc_type
        self.exc_value = exc_value
        if not isinstance(exc_type, str):
            exception_type = exc_type.__name__
            if exc_type.__module__ not in ('__builtin__', 'exceptions'):
                exception_type = exc_type.__module__ + '.' + exception_type
        else:
            exception_type = exc_type
        self.exception_type = exception_type
        self.frames = []
        while tb:
            self.frames.append(Frame(exc_type, exc_value, tb))
            tb = tb.tb_next

    def is_syntax_error(self):
        """Is it a syntax error?"""
        return isinstance(self.exc_value, SyntaxError)
    is_syntax_error = property(is_syntax_error)

    def exception(self):
        """String representation of the exception."""
        buf = traceback.format_exception_only(self.exc_type, self.exc_value)
        return ''.join(buf).strip().decode('utf-8', 'replace')
    exception = property(exception)

    def log(self, logfile=None):
        """Log the ASCII traceback into a file object."""
        if logfile is None:
            logfile = sys.stderr
        tb = self.plaintext.encode('utf-8', 'replace').rstrip() + '\n'
        logfile.write(tb)

    def paste(self):
        """Create a paste and return the paste id."""
        from xmlrpclib import ServerProxy
        srv = ServerProxy('http://paste.pocoo.org/xmlrpc/')
        return srv.pastes.newPaste('pytb', self.plaintext)
        return '{"url": "http://paste.pocoo.org/show/%d/", "id": %d}' % \
               (paste_id, paste_id)

    def render_summary(self, include_title=True):
        """Render the traceback for the interactive console."""
        return render_template('traceback_summary.html', traceback=self,
                               include_title=include_title)

    def render_full(self):
        """Render the Full HTML page with the traceback info."""
        return render_template('traceback_full.html', traceback=self)

    def plaintext(self):
        return render_template('traceback_plaintext.html', traceback=self)
    plaintext = cached_property(plaintext)

    id = property(lambda x: id(x))


class Frame(object):
    """A single frame in a traceback."""

    def __init__(self, exc_type, exc_value, tb):
        self.lineno = tb.tb_lineno
        self.function_name = tb.tb_frame.f_code.co_name
        self.locals = tb.tb_frame.f_locals
        self.globals = tb.tb_frame.f_globals

        fn = inspect.getsourcefile(tb) or inspect.getfile(tb)
        if fn[-4:] in ('.pyo', '.pyc'):
            fn = fn[:-1]
        if fn != '<debugger>':
            fn = os.path.realpath(fn)
        self.filename = fn
        self.module = self.globals.get('__name__')
        self.loader = self.globals.get('__loader__')
        self.code = tb.tb_frame.f_code

    def render(self):
        """Render a single frame in a traceback."""
        return render_template('frame.html', frame=self)

    def render_source(self):
        """Render the sourcecode."""
        lines = [Line(idx + 1, x) for idx, x in enumerate(self.sourcelines)]

        # find function definition and mark lines
        if hasattr(self.code, 'co_firstlineno'):
            lineno = self.code.co_firstlineno - 1
            while lineno > 0:
                if _funcdef_re.match(lines[lineno].code):
                    break
                lineno -= 1
            offset = len(inspect.getblock([x.code + '\n' for x in lines[lineno:]]))
            for line in lines[lineno:lineno + offset]:
                line.in_frame = True

        # mark current line
        try:
            lines[self.lineno - 1].current = True
        except IndexError:
            pass

        return render_template('source.html', frame=self, lines=lines)

    def eval(self, code, mode='single'):
        """Evaluate code in the context of the frame."""
        if isinstance(code, basestring):
            if isinstance(code, unicode):
                code = UTF8_COOKIE + code.encode('utf-8')
            code = compile(code, '<interactive>', mode)
        if mode != 'exec':
            return eval(code, self.globals, self.locals)
        exec code in self.globals, self.locals

    def sourcelines(self):
        """The sourcecode of the file as list of unicode strings."""
        # get sourcecode from loader or file
        source = None
        if self.loader is not None:
            if hasattr(self.loader, 'get_source'):
                source = self.loader.get_source(self.module)
            elif hasattr(self.loader, 'get_source_by_code'):
                source = self.loader.get_source_by_code(self.code)
        if source is None:
            try:
                f = file(self.filename)
            except IOError:
                return []
            try:
                source = f.read()
            finally:
                f.close()

        # already unicode?  return right away
        if isinstance(source, unicode):
            return source.splitlines()

        # yes. it should be ascii, but we don't want to reject too many
        # characters in the debugger if something breaks
        charset = 'utf-8'
        if source.startswith(UTF8_COOKIE):
            source = source[3:]
        else:
            for idx, match in enumerate(_line_re.finditer(source)):
                match = _line_re.search(match.group())
                if match is not None:
                    charset = match.group(1)
                    break
                if idx > 1:
                    break

        # on broken cookies we fall back to utf-8 too
        try:
            codecs.lookup(charset)
        except LookupError:
            charset = 'utf-8'

        return source.decode(charset, 'replace').splitlines()
    sourcelines = cached_property(sourcelines)

    def current_line(self):
        try:
            return self.sourcelines[self.lineno - 1]
        except IndexError:
            return u''
    current_line = property(current_line)

    def console(self):
        return Console(self.globals, self.locals)
    console = cached_property(console)

    id = property(lambda x: id(x))
