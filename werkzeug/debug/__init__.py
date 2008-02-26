# -*- coding: utf-8 -*-
"""
    werkzeug.debug
    ~~~~~~~~~~~~~~

    WSGI application traceback debugger.

    :copyright: 2008 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.debug.repr import debug_repr
from werkzeug.debug.tbtools import get_current_traceback


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

    def __init__(self, app, evalex=False, request_key='werkzeug.request'):
        pass
