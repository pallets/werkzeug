# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite
    ~~~~~~~~~~~~~~~~~~

    Contains all test Werkzeug tests.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement

import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import six
from werkzeug.utils import import_string, find_modules


def iter_suites(package):
    """Yields all testsuites."""
    for module in find_modules(package, include_packages=True):
        mod = __import__(module, fromlist=['*'])
        if hasattr(mod, 'suite'):
            yield mod.suite()


def find_all_tests(suite):
    """Yields all the tests and their names from a given suite."""
    suites = [suite]
    while suites:
        s = suites.pop()
        try:
            suites.extend(s)
        except TypeError:
            yield s, '%s.%s.%s' % (
                s.__class__.__module__,
                s.__class__.__name__,
                s._testMethodName
            )


class WerkzeugTestCase(unittest.TestCase):
    """Baseclass for all the tests that Werkzeug uses.  Use these
    methods for testing instead of the camelcased ones in the
    baseclass for consistency.
    """

    def setup(self):
        pass

    def teardown(self):
        pass

    def setUp(self):
        self.setup()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        self.teardown()

    def assert_line_equal(self, x, y):
        assert x == y, "lines not equal\n a = %r\n b = %r" % (x, y)

    def assert_equal(self, x, y):
        return self.assertEqual(x, y)

    def assert_not_equal(self, x, y):
        return self.assertNotEqual(x, y)

    def assert_raises(self, exc_type, callable=None, *args, **kwargs):
        catcher = _ExceptionCatcher(self, exc_type)
        if callable is None:
            return catcher
        with catcher:
            callable(*args, **kwargs)

    if not six.PY3:
        def assertRaisesRegex(self, *args, **kwargs):
            return self.assertRaisesRegexp(*args, **kwargs)

    if sys.version_info[:2] == (2, 6):
        def assert_is_none(self, x):
            assert x is None, "%r is not None" % (x,)

        def assert_is_not_none(self, x):
            assert x is not None, "%r is None" % (x, )

        def assert_in(self, x, y):
            assert x in y, "%r not in %r" % (x, y)

        def assert_not_in(self, x, y):
            assert x not in y, "%r in %r" % (x, y)

        def assert_is_instance(self, x, y):
            assert isinstance(x, y), "not isinstance(%r, %r)" % (x, y)

        def assert_is(self, x, y):
            assert x is y, "%r is not %r" % (x, y)

        def assert_is_not(self, x, y):
            assert x is not y, "%r is %r" % (x, y)
    else:
        def assert_is_none(self, x):
            return self.assertIsNone(x)

        def assert_is_not_none(self, x):
            return self.assertIsNotNone(x)

        def assert_in(self, x, y):
            return self.assertIn(x, y)

        def assert_is_instance(self, x, y):
            return self.assertIsInstance(x, y)

        def assert_not_in(self, x, y):
            return self.assertNotIn(x, y)

        def assert_is(self, x, y):
            return self.assertIs(x, y)

        def assert_is_not(self, x, y):
            return self.assertIsNot(x, y)

    def assert_true(self, x):
        return self.assertTrue(x)

    def assert_false(self, x):
        return self.assertFalse(x)

    def assert_strict_equal(self, x, y):
        '''Stricter version of assert_equal that doesn't do implicit conversion
        between unicode and strings'''
        self.assert_equal(x, y)
        assert issubclass(type(x), type(y)) or issubclass(type(y), type(x)), \
                '%s != %s' % (type(x), type(y))
        if isinstance(x, (six.binary_type, six.text_type, six.integer_types)) or x is None:
            return
        elif isinstance(x, dict) or isinstance(y, dict):
            x = sorted(x.items())
            y = sorted(y.items())
        elif isinstance(x, set) or isinstance(y, set):
            x = sorted(x)
            y = sorted(y)
        self.assert_equal(repr(x), repr(y))


class _ExceptionCatcher(object):

    def __init__(self, test_case, exc_type):
        self.test_case = test_case
        self.exc_type = exc_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        exception_name = self.exc_type.__name__
        if exc_type is None:
            self.test_case.fail('Expected exception of type %r' %
                                exception_name)
        elif not issubclass(exc_type, self.exc_type):
            six.reraise(exc_type, exc_value, tb)
        return True


class BetterLoader(unittest.TestLoader):
    """A nicer loader that solves two problems.  First of all we are setting
    up tests from different sources and we're doing this programmatically
    which breaks the default loading logic so this is required anyways.
    Secondly this loader has a nicer interpolation for test names than the
    default one so you can just do ``run-tests.py ViewTestCase`` and it
    will work.
    """

    def getRootSuite(self):
        return suite()

    def loadTestsFromName(self, name, module=None):
        root = self.getRootSuite()
        if name == 'suite':
            return root

        all_tests = []
        for testcase, testname in find_all_tests(root):
            if testname == name or \
               testname.endswith('.' + name) or \
               ('.' + name + '.') in testname or \
               testname.startswith(name + '.'):
                all_tests.append(testcase)

        if not all_tests:
            raise LookupError('could not find test case for "%s"' % name)

        if len(all_tests) == 1:
            return all_tests[0]
        rv = unittest.TestSuite()
        for test in all_tests:
            rv.addTest(test)
        return rv


def suite():
    """A testsuite that has all the Flask tests.  You can use this
    function to integrate the Flask tests into your own testsuite
    in case you want to test that monkeypatches to Flask do not
    break it.
    """
    suite = unittest.TestSuite()
    for other_suite in iter_suites(__name__):
        suite.addTest(other_suite)
    return suite


def main():
    """Runs the testsuite as command line application."""
    try:
        unittest.main(testLoader=BetterLoader(), defaultTest='suite')
    except Exception:
        import sys
        import traceback
        traceback.print_exc()
        sys.exit(1)

