import copy
import time
from functools import partial
from threading import Thread

import pytest

from werkzeug import local


def test_basic_local():
    ns = local.Local()
    ns.foo = 0
    values = []

    def value_setter(idx):
        time.sleep(0.01 * idx)
        ns.foo = idx
        time.sleep(0.02)
        values.append(ns.foo)

    threads = [Thread(target=value_setter, args=(x,)) for x in [1, 2, 3]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(values) == [1, 2, 3]

    def delfoo():
        del ns.foo

    delfoo()
    pytest.raises(AttributeError, lambda: ns.foo)
    pytest.raises(AttributeError, delfoo)

    local.release_local(ns)


def test_local_release():
    ns = local.Local()
    ns.foo = 42
    local.release_local(ns)
    assert not hasattr(ns, "foo")

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
    assert str(foo) == str(ls)
    assert dir(foo) == dir(ls)
    assert foo[0] == 42
    foo += [1]
    assert list(foo) == [42, 1, 2, 3, 1]


def test_local_proxy_operations_math():
    foo = 2
    ls = local.LocalProxy(lambda: foo)

    assert ls < 3
    assert ls <= 3
    assert not ls < 1
    assert not ls <= 1
    assert ls == 2
    assert ls != 3
    assert ls > 1
    assert ls >= 1
    assert not ls > 3
    assert not ls >= 3

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
    assert divmod(ls, 2) == (1, 0)
    assert divmod(2, ls) == (1, 0)
    assert ls ** 3 == 8
    assert 3 ** ls == 9

    assert ls << 3 == 16
    assert 3 << ls == 12
    assert ls >> 1 == 1
    assert 8 >> ls == 2
    assert ls & 3 == 2
    assert 3 & ls == 2
    assert ls ^ 3 == 1
    assert 3 ^ ls == 1
    assert ls | 1 == 3
    assert 1 | ls == 3

    with pytest.raises(TypeError):
        ls += 1
    with pytest.raises(TypeError):
        ls -= 1
    with pytest.raises(TypeError):
        ls *= 2
    with pytest.raises(TypeError):
        ls /= 2
    with pytest.raises(TypeError):
        ls //= 2
    with pytest.raises(TypeError):
        ls %= 2
    with pytest.raises(TypeError):
        ls **= 2
    with pytest.raises(TypeError):
        ls <<= 1
    with pytest.raises(TypeError):
        ls >>= 1
    with pytest.raises(TypeError):
        ls &= 1
    with pytest.raises(TypeError):
        ls ^= 1
    with pytest.raises(TypeError):
        ls |= 1

    assert -ls == -2
    assert +ls == 2
    assert abs(ls) == 2
    assert ~ls == -3

    assert isinstance(complex(ls), complex)
    assert complex(ls) == 2
    assert isinstance(int(ls), int)
    assert int(ls) == 2
    assert isinstance(float(ls), float)
    assert float(ls) == 2

    assert bin(ls) == "0b10"
    assert oct(ls) == "0o2"
    assert hex(ls) == "0x2"

    import operator
    from functools import partialmethod

    def iop(self, other, op):
        self.i = op(self.i, other)
        return self

    class MutableInt:
        def __init__(self, i):
            self.i = i

        def __eq__(self, other):
            return self.i == other

        __iadd__ = partialmethod(iop, op=operator.add)
        __isub__ = partialmethod(iop, op=operator.sub)
        __imul__ = partialmethod(iop, op=operator.mul)
        __itruediv__ = partialmethod(iop, op=operator.truediv)
        __ifloordiv__ = partialmethod(iop, op=operator.floordiv)
        __imod__ = partialmethod(iop, op=operator.mod)
        __ipow__ = partialmethod(iop, op=operator.pow)
        __ilshift__ = partialmethod(iop, op=operator.lshift)
        __irshift__ = partialmethod(iop, op=operator.rshift)
        __iand__ = partialmethod(iop, op=operator.and_)
        __ixor__ = partialmethod(iop, op=operator.xor)
        __ior__ = partialmethod(iop, op=operator.or_)

    foo = MutableInt(2)
    ls += 1
    assert ls == 3
    assert foo == 3

    foo = MutableInt(2)
    ls -= 1
    assert ls == 1
    assert foo == 1

    foo = MutableInt(2)
    ls *= 1
    assert ls == 2
    assert foo == 2

    foo = MutableInt(2)
    ls /= 1
    assert ls == 2
    assert foo == 2

    foo = MutableInt(2)
    ls //= 1.0
    assert ls == 2.0
    assert foo == 2.0

    foo = MutableInt(2)
    ls %= 2
    assert ls == 0
    assert foo == 0

    foo = MutableInt(2)
    ls **= 3
    assert ls == 8
    assert foo == 8

    foo = MutableInt(2)
    ls <<= 3
    assert ls == 16
    assert foo == 16

    foo = MutableInt(2)
    ls >>= 1
    assert ls == 1
    assert foo == 1

    foo = MutableInt(2)
    ls &= 3
    assert ls == 2
    assert foo == 2

    foo = MutableInt(2)
    ls ^= 3
    assert ls == 1
    assert foo == 1

    foo = MutableInt(2)
    ls |= 1
    assert ls == 3
    assert foo == 3


def test_local_proxy_nums():
    foo = 2
    ls = local.LocalProxy(lambda: foo)

    assert isinstance(ls, int)
    assert [1, 2, 3][ls] == 3

    foo = "2"
    assert int(ls) == 2

    foo = "2.5"
    assert float(ls) == 2.5

    class Index:
        def __init__(self, i):
            self.i = i

        def __eq__(self, other):
            return isinstance(other, Index)

        def __ne__(self, other):
            return isinstance(other, Index)

        def __complex__(self):
            return self.i + 1j

        def __int__(self):
            return self.i - 1

        def __float__(self):
            return self.i + 0.5

        def __index__(self):
            return self.i

        def __round__(self, n=None):
            if n is None:
                return None
            return self.i + n

        def __trunc__(self):
            return self.i + 1

        def __floor__(self):
            return self.i + 2

        def __ceil__(self):
            return self.i + 3

    foo = Index(2)
    bar = Index(2)

    assert ls == bar
    assert ls != bar

    assert complex(ls) == 2 + 1j
    assert int(ls) == 1
    assert float(ls) == 2.5

    assert bin(ls) == "0b10"
    assert oct(ls) == "0o2"
    assert hex(ls) == "0x2"
    assert [1, 2, 3][ls] == 3

    from math import trunc, floor, ceil

    assert round(ls) is None
    assert round(ls, 0) == 2
    assert trunc(ls) == 3
    assert floor(ls) == 4
    assert ceil(ls) == 5


def test_local_proxy_operations_strings():
    foo = "foo"
    ls = local.LocalProxy(lambda: foo)

    assert ls + "bar" == "foobar"
    assert "bar" + ls == "barfoo"
    assert ls * 2 == "foofoo"

    assert format(ls, "s") == "foo"
    assert hash(ls) == hash(foo)
    assert bool(ls)

    foo = ""

    assert not bool(ls)

    foo = "foo %s"
    assert ls % ("bar",) == "foo bar"

    foo = "foo {}"
    assert ls.format("bar") == "foo bar"


def test_local_proxy_lists():
    foo = [1, 2, 3]
    ls = local.LocalProxy(lambda: foo)

    assert len(ls) == 3
    assert ls[0] == 1

    ls[0] = 4
    assert ls == [4, 2, 3]
    assert foo == [4, 2, 3]
    foo = [1, 2, 3]

    del ls[1]
    assert ls == [1, 3]
    assert foo == [1, 3]
    foo = [1, 2, 3]

    assert list(ls) == [1, 2, 3]
    assert list(reversed(ls)) == [3, 2, 1]
    assert 2 in ls
    assert 4 not in ls

    ls += [4, 5, 6]
    assert ls == [1, 2, 3, 4, 5, 6]
    assert foo == [1, 2, 3, 4, 5, 6]
    foo = [1, 2, 3]

    ls *= 2
    assert ls == [1, 2, 3, 1, 2, 3]
    assert foo == [1, 2, 3, 1, 2, 3]


def test_local_proxy_dicts():
    class SomeDictSubclass(dict):
        def __missing__(self, key):
            return key

    foo = SomeDictSubclass()
    ls = local.LocalProxy(lambda: foo)

    assert ls[1] == 1
    assert ls.__missing__(2) == 2


def test_local_proxy_iterable():
    class SomeIterable:
        def __iter__(self):
            yield from range(3)

    foo = SomeIterable()
    ls = local.LocalProxy(lambda: foo)

    assert list(ls) == [0, 1, 2]
    assert list(ls) == [0, 1, 2]
    assert list(foo) == [0, 1, 2]


def test_local_proxy_iterator():
    class SomeIterator:
        def __init__(self):
            self.val = 0

        def __next__(self):
            self.val += 1
            return self.val

        def __reversed__(self):
            return self

    foo = SomeIterator()
    ls = local.LocalProxy(lambda: foo)

    assert next(ls) == 1
    assert next(foo) == 2
    assert next(foo) == 3
    assert next(ls) == 4
    assert next(reversed(ls)) == 5


def test_local_proxy_classes():
    class SomeMetaClass(type):
        def __instancecheck__(cls, instance):
            return True

        def __subclasscheck__(cls, subclass):
            return True

    class SomeParentClass:
        pass

    class SomeClass(SomeParentClass, metaclass=SomeMetaClass):
        pass

    class SomeChildClass(SomeClass):
        pass

    ls = local.LocalProxy(lambda: SomeClass)

    assert type(ls()) is SomeClass
    assert isinstance(1, ls)
    assert issubclass(int, ls)
    assert ls.__mro__ == (SomeClass, SomeParentClass, object)
    assert ls.__bases__ == (SomeParentClass,)
    assert ls.__subclasses__() == [SomeChildClass]


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
    assert repr(proxy) == "<LocalProxy unbound>"
    assert proxy.__doc__.startswith("Acts as a proxy")
    assert not proxy
    assert dir(proxy) == []

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
    ns = local.Local()
    stack = local.LocalStack()
    local.LocalManager([ns, stack], ident_func=lambda: ident)

    ns.foo = 42
    stack.push({"foo": 42})
    ident = 1
    ns.foo = 23
    stack.push({"foo": 23})
    ident = 0
    assert ns.foo == 42
    assert stack.top["foo"] == 42
    stack.pop()
    assert stack.top is None
    ident = 1
    assert ns.foo == 23
    assert stack.top["foo"] == 23
    stack.pop()
    assert stack.top is None


def test_local_proxy_string_representations():
    class SomeClass(str):
        def __bytes__(self):
            return self.encode("utf-8")

    foo = SomeClass("foo")
    ls = local.LocalProxy(lambda: foo)

    assert repr(ls) == "'foo'"
    assert str(ls) == "foo"
    assert bytes(ls) == b"foo"


def test_local_proxy_custom_attributes():
    class SomeClass:
        def __init__(self):
            object.__setattr__(self, "vals", {})

        def __getattr__(self, item):
            return self.vals.get(item, item)

        def __getattribute__(self, item):
            if item == "ham":
                return "eggs"

            return object.__getattribute__(self, item)

        def __setattr__(self, key, value):
            self.vals[key] = value

        def __delattr__(self, item):
            del self.vals[item]

        def __dir__(self):
            return self.vals.keys()

    foo = SomeClass()
    ls = local.LocalProxy(lambda: foo)

    assert ls.bar == "bar"
    assert ls.__dict__ == {"vals": {}}
    assert vars(ls) == {"vals": {}}
    assert dir(ls) == []

    ls.bar = "baz"
    assert ls.bar == "baz"
    assert ls.__dict__ == {"vals": {"bar": "baz"}}
    assert vars(ls) == {"vals": {"bar": "baz"}}
    assert dir(ls) == ["bar"]

    del ls.bar
    assert ls.bar == "bar"
    assert ls.__dict__ == {"vals": {}}
    assert vars(ls) == {"vals": {}}
    assert dir(ls) == []

    assert ls.ham == "eggs"
    ls.ham = "green eggs"
    assert ls.ham == "eggs"
    assert ls.vals["ham"] == "green eggs"


def test_local_proxy_enum():
    from enum import Enum, auto

    class Color(Enum):
        RED = auto()
        BLUE = auto()
        GREEN = auto()

    ls = local.LocalProxy(lambda: Color)

    assert ls.__members__ == Color.__members__


def test_local_proxy_descriptor():
    class NamedProperty(property):
        def __set_name__(self, owner, name):
            self.name = name

    @NamedProperty
    def x_prop(self):
        return self._x

    @x_prop.setter
    def x_prop(self, value):
        self._x = value

    @x_prop.deleter
    def x_prop(self):
        self._x = None

    ls = local.LocalProxy(lambda: x_prop)

    class SomeClass:
        def __init__(self, val):
            self._x = val

        x = ls

    assert SomeClass.x.name == "x"

    foo = SomeClass("foo")

    assert foo.x == "foo"

    foo.x = "bar"
    assert foo.x == "bar"
    assert foo._x == "bar"

    del foo.x
    assert foo.x is None
    assert foo._x is None


def test_local_proxy_callable():
    i = 1

    def foo(x: int = 0, *, y=0) -> int:
        """Lorem ipsum"""
        return x + y + i

    ls = local.LocalProxy(lambda: foo)

    assert ls(1) == 2
    assert ls.__doc__ == "Lorem ipsum"
    assert ls.__qualname__ == "test_local_proxy_callable.<locals>.foo"
    assert ls.__module__ == "werkzeug.local"
    assert ls.__defaults__ == (0,)
    assert ls.__code__ == foo.__code__
    assert ls.__globals__ == globals()
    assert ls.__closure__ == foo.__closure__
    assert ls.__annotations__ == {"x": int, "return": int}
    assert ls.__kwdefaults__ == {"y": 0}

    class SomeClass:
        def bar(self):
            """Dolor sit amet"""
            return 10

    some_instance = SomeClass()
    foo = some_instance.bar

    assert ls() == 10
    assert ls.__self__ is some_instance
    assert ls.__func__ is SomeClass.bar
    assert ls.__doc__ == "Dolor sit amet"
    assert ls.__module__ == "werkzeug.local"


def test_local_proxy_length_hint():
    from operator import length_hint

    class SomeClassWithLengthHint:
        def __init__(self, lst):
            self.lst = lst

        def __length_hint__(self):
            return len(self.lst)

    foo = SomeClassWithLengthHint([1, 2, 3])
    ls = local.LocalProxy(lambda: foo)

    assert length_hint(ls) == 3


def test_local_proxy_contains():
    class SomeContainer:
        def __contains__(self, item):
            return item == 1

    foo = SomeContainer()
    ls = local.LocalProxy(lambda: foo)

    assert 1 in ls
    assert 2 not in ls


def test_local_proxy_matmul():
    class SomeMatrix:
        def __init__(self, val):
            self.val = val

        def __matmul__(self, other):
            return SomeMatrix(self.val * other)

        def __rmatmul__(self, other):
            return SomeMatrix(self.val * other)

        def __imatmul__(self, other):
            self.val += other
            return self

        def __eq__(self, other):
            return self.val == other.val

    foo = SomeMatrix(2)
    ls = local.LocalProxy(lambda: foo)

    assert ls @ 3 == SomeMatrix(6)
    assert 3 @ ls == SomeMatrix(6)

    ls @= 3
    assert ls == SomeMatrix(5)


def test_local_proxy_context_manager():
    class SomeContextManager:
        def __init__(self, val):
            self.val = val

        def __enter__(self):
            self.val += 1

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.val -= 1

    foo = SomeContextManager(2)
    ls = local.LocalProxy(lambda: foo)

    assert ls.val == 2

    with ls:
        assert ls.val == 3

    assert ls.val == 2


def test_deepcopy_on_proxy():
    class Foo:
        attr = 42

        def __copy__(self):
            return self

        def __deepcopy__(self, memo):
            return self

    f = Foo()
    p = local.LocalProxy(lambda: f)
    assert p.attr == 42
    assert copy.deepcopy(p) is f
    assert copy.copy(p) is f

    a = []
    p2 = local.LocalProxy(lambda: [a])
    assert copy.copy(p2) == [a]
    assert copy.copy(p2)[0] is a

    assert copy.deepcopy(p2) == [a]
    assert copy.deepcopy(p2)[0] is not a


def test_local_proxy_wrapped_attribute():
    class SomeClassWithWrapped:
        __wrapped__ = "wrapped"

    def lookup_func():
        return 42

    partial_lookup_func = partial(lookup_func)

    proxy = local.LocalProxy(lookup_func)
    assert proxy.__wrapped__ is lookup_func

    partial_proxy = local.LocalProxy(partial_lookup_func)
    assert partial_proxy.__wrapped__ == partial_lookup_func

    ns = local.Local()
    ns.foo = SomeClassWithWrapped()
    ns.bar = 42

    assert ns("foo").__wrapped__ == "wrapped"
    pytest.raises(AttributeError, lambda: ns("bar").__wrapped__)
