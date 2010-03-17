# -*- coding: utf-8 -*-
"""
    werkzeug.local test
    ~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import time
from threading import Thread

from nose.tools import assert_raises

from werkzeug import Local, LocalManager


def test_basic_local():
    """Basic local object support"""
    l = Local()
    l.foo = 0
    values = []
    def value_setter(idx):
        time.sleep(0.01 * idx)
        l.foo = idx
        time.sleep(0.02)
        values.append(l.foo)
    threads = [Thread(target=value_setter, args=(x,))
               for x in [1, 2, 3]]
    for thread in threads:
        thread.start()
    time.sleep(0.2)
    assert sorted(values) == [1, 2, 3]

    def delfoo():
        del l.foo
    delfoo()
    assert_raises(AttributeError, lambda: l.foo)
    assert_raises(AttributeError, delfoo)
