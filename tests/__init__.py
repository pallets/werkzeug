# -*- coding: utf-8 -*-
"""
    tests
    ~~~~~

    Contains all test Werkzeug tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement

from werkzeug._compat import text_type


def strict_eq(x, y):
    '''Equality test bypassing the implicit string conversion in Python 2'''
    __tracebackhide__ = True
    assert x == y
    assert issubclass(type(x), type(y)) or issubclass(type(y), type(x))
    if isinstance(x, dict) and isinstance(y, dict):
        x = sorted(x.items())
        y = sorted(y.items())
    elif isinstance(x, set) and isinstance(y, set):
        x = sorted(x)
        y = sorted(y)
    assert repr(x) == repr(y)
