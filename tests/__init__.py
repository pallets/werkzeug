# -*- coding: utf-8 -*-
"""
    tests
    ~~~~~

    Contains all test Werkzeug tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement

from werkzeug._compat import text_type, integer_types


class WerkzeugTests(object):
    """Baseclass for all the tests that Werkzeug uses.  Use these
    methods for testing instead of the camelcased ones in the
    baseclass for consistency.
    """

    def assert_equal(self, x, y, msg=None):
        assert x == y, msg

    def assert_strict_equal(self, x, y):
        '''Stricter version of assert_equal that doesn't do implicit conversion
        between unicode and strings'''
        assert x == y
        assert issubclass(type(x), type(y)) or issubclass(type(y), type(x)), \
            '%s != %s' % (type(x), type(y))
        if isinstance(x, (bytes, text_type, integer_types)) or x is None:
            return
        elif isinstance(x, dict) or isinstance(y, dict):
            x = sorted(x.items())
            y = sorted(y.items())
        elif isinstance(x, set) or isinstance(y, set):
            x = sorted(x)
            y = sorted(y)
        rx, ry = repr(x), repr(y)
        if rx != ry:
            rx = rx[:200] + (rx[200:] and '...')
            ry = ry[:200] + (ry[200:] and '...')
            raise AssertionError(rx, ry)
        assert repr(x) == repr(y), repr((x, y))[:200]
