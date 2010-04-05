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

from werkzeug import Local, LocalManager, LocalStack, LocalProxy, release_local


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

    release_local(l)


def test_local_release():
    """Locals work without manager"""
    loc = Local()
    loc.foo = 42
    release_local(loc)
    assert not hasattr(loc, 'foo')

    ls = LocalStack()
    ls.push(42)
    release_local(ls)
    assert ls.top is None


def test_local_stack():
    """Test the LocalStack"""
    ls = LocalStack()
    assert ls.top is None
    ls.push(42)
    assert ls.top == 42
    ls.push(23)
    assert ls.top == 23
    ls.pop()
    assert ls.top == 42
    ls.pop()
    assert ls.top is None
    assert ls.pop() is None
    assert ls.pop() is None

    proxy = ls()
    ls.push([1, 2])
    assert proxy == [1, 2]
    ls.push((1, 2))
    assert proxy == (1, 2)
    ls.pop()
    ls.pop()
    assert repr(proxy) == '<LocalProxy unbound>'

    release_local(ls)


def test_local_proxies_with_callables():
    """Use a callable with a local proxy"""
    foo = 42
    ls = LocalProxy(lambda: foo)
    assert ls == 42
    foo = [23]
    ls.append(42)
    assert ls == [23, 42]
    assert foo == [23, 42]
