# -*- coding: utf-8 -*-
"""
    conftest
    ~~~~~~~~

    Configure py.test for support stuff.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import py


class Module(py.test.collect.Module):

    def __init__(self, *args, **kwargs):
        super(Module, self).__init__(*args, **kwargs)

    def makeitem(self, name, obj, usefilters=True):
        if name.startswith('test_'):
            if hasattr(obj, 'func_code'):
                return WerkzeugTestFunction(name, parent=self)
            elif isinstance(obj, basestring):
                return WerkzeugDocTest(name, parent=self)


class WerkzeugTestFunction(py.test.collect.Function):

    def execute(self, target, *args):
        target(*args)


class WerkzeugDocTest(py.test.collect.Item):

    def run(self):
        mod = py.std.types.ModuleType(self.name)
        mod.__doc__ = self.obj
        self.execute(mod)

    def execute(self, mod):
        mod.MODULE = self.parent.obj
        failed, tot = py.compat.doctest.testmod(mod, verbose=True)
        if failed:
            py.test.fail('doctest %s: %s failed out of %s' % (
                         self.fspath, failed, tot))
