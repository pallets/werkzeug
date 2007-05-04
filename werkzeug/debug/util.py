# -*- coding: utf-8 -*-
"""
    werkzeug.debug.util
    ~~~~~~~~~~~~~~~~~~~

    Debugging utilities.

    :copyright: 2007 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import inspect
import threading
from random import random
from cStringIO import StringIO

from werkzeug.debug.highlighter import PythonParser


def get_current_thread():
    return threading.currentThread()


class Namespace(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class ThreadedStream(object):
    _orig = None

    def __init__(self):
        self._buffer = {}

    def install(cls, environ):
        if cls._orig or not environ['wsgi.multithread']:
            return
        cls._orig = sys.stdout
        sys.stdout = cls()
    install = classmethod(install)

    def can_interact(cls):
        return not cls._orig is None
    can_interact = classmethod(can_interact)

    def push(self):
        tid = get_current_thread()
        self._buffer[tid] = StringIO()

    def release(self):
        tid = get_current_thread()
        if tid in self._buffer:
            result = self._buffer[tid].getvalue()
            del self._buffer[tid]
        else:
            result = ''
        return result

    def write(self, d):
        tid = get_current_thread()
        if tid in self._buffer:
            self._buffer[tid].write(d)
        else:
            self._orig.write(d)


def get_uid():
    """
    Return a random unique ID.
    """
    return str(random()).encode('base64')[3:11]


def get_frame_info(tb, context_lines=7):
    """
    Return a dict of information about a given traceback.
    """
    # line numbers / function / variables
    lineno = tb.tb_lineno
    function = tb.tb_frame.f_code.co_name
    variables = tb.tb_frame.f_locals

    # get filename
    fn = tb.tb_frame.f_globals.get('__file__')
    if not fn:
        fn = os.path.realpath(inspect.getsourcefile(tb) or
                              inspect.getfile(tb))
    if fn[-4:] in ('.pyc', '.pyo'):
        fn = fn[:-1]

    # module name
    modname = tb.tb_frame.f_globals.get('__name__')

    # get loader
    loader = tb.tb_frame.f_globals.get('__loader__')

    # sourcecode
    try:
        if not loader is None:
            source = loader.get_source(modname)
        else:
            source = file(fn).read()
    except:
        source = ''
        pre_context, post_context = [], []
        context_line, context_lineno = None, None
    else:
        parser = PythonParser(source)
        parser.parse()
        parsed_source = parser.get_html_output()
        lbound = max(0, lineno - context_lines - 1)
        ubound = lineno + context_lines
        try:
            context_line = parsed_source[lineno - 1]
            pre_context = parsed_source[lbound:lineno - 1]
            post_context = parsed_source[lineno:ubound]
        except IndexError, e:
            context_line = None
            pre_context = post_context = [], []
        context_lineno = lbound

    return {
        'tb':               tb,
        'filename':         isinstance(fn, unicode) and fn.encode('utf-8') or fn,
        'loader':           loader,
        'function':         function,
        'lineno':           lineno,
        'vars':             variables,
        'pre_context':      pre_context,
        'context_line':     context_line,
        'post_context':     post_context,
        'context_lineno':   context_lineno,
        'source':           source
    }
