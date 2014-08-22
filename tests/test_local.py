# -*- coding: utf-8 -*-
"""
    tests.local
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Local and local proxy tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

import time
from threading import Thread

from werkzeug import local


def test_basic_local():
    l = local.Local()
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
    pytest.raises(AttributeError, lambda: l.foo)
    pytest.raises(AttributeError, delfoo)

    local.release_local(l)

def test_local_release():
    l = local.Local()
    l.foo = 42
    local.release_local(l)
    assert not hasattr(l, 'foo')

    ls = local.LocalStack()
    ls.push(42)
    local.release_local(ls)
    assert ls.top is None

def test_local_proxy():
    foo = []
    ls = local.LocalProxy(lambda: foo)
    ls.append(42)
    ls.append(23)
    ls[1:] = [1, 2, 3]
    assert foo == [42, 1, 2, 3]
    assert repr(foo) == repr(ls)
    assert foo[0] == 42
    foo += [1]
    assert list(foo) == [42, 1, 2, 3, 1]

def test_local_proxy_operations_math():
    foo = 2
    ls = local.LocalProxy(lambda: foo)
    assert ls + 1 == 3
    assert 1 + ls == 3
    assert ls - 1 == 1
    assert 1 - ls == -1
    assert ls * 1 == 2
    assert 1 * ls == 2
    assert ls / 1 == 2
    assert 1.0 / ls == 0.5
    assert ls // 1.0 == 2.0
    assert 1.0 // ls == 0.0
    assert ls % 2 == 0
    assert 2 % ls == 0

def test_local_proxy_operations_strings():
    foo = "foo"
    ls = local.LocalProxy(lambda: foo)
    assert ls + "bar" == "foobar"
    assert "bar" + ls == "barfoo"
    assert ls * 2 == "foofoo"

    foo = "foo %s"
    assert ls % ("bar",) == "foo bar"

def test_local_stack():
    ident = local.get_ident()

    ls = local.LocalStack()
    assert ident not in ls._local.__storage__
    assert ls.top is None
    ls.push(42)
    assert ident in ls._local.__storage__
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

    assert ident not in ls._local.__storage__

def test_local_proxies_with_callables():
    foo = 42
    ls = local.LocalProxy(lambda: foo)
    assert ls == 42
    foo = [23]
    ls.append(42)
    assert ls == [23, 42]
    assert foo == [23, 42]

def test_custom_idents():
    ident = 0
    l = local.Local()
    stack = local.LocalStack()
    mgr = local.LocalManager([l, stack], ident_func=lambda: ident)

    l.foo = 42
    stack.push({'foo': 42})
    ident = 1
    l.foo = 23
    stack.push({'foo': 23})
    ident = 0
    assert l.foo == 42
    assert stack.top['foo'] == 42
    stack.pop()
    assert stack.top is None
    ident = 1
    assert l.foo == 23
    assert stack.top['foo'] == 23
    stack.pop()
    assert stack.top is None
