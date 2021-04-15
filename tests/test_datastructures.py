import io
import pickle
import tempfile
import typing as t
from contextlib import contextmanager
from copy import copy
from copy import deepcopy

import pytest

from werkzeug import datastructures as ds
from werkzeug import http
from werkzeug.exceptions import BadRequestKeyError


class TestNativeItermethods:
    def test_basic(self):
        class StupidDict:
            def keys(self, multi=1):
                return iter(["a", "b", "c"] * multi)

            def values(self, multi=1):
                return iter([1, 2, 3] * multi)

            def items(self, multi=1):
                return iter(
                    zip(iter(self.keys(multi=multi)), iter(self.values(multi=multi)))
                )

        d = StupidDict()
        expected_keys = ["a", "b", "c"]
        expected_values = [1, 2, 3]
        expected_items = list(zip(expected_keys, expected_values))

        assert list(d.keys()) == expected_keys
        assert list(d.values()) == expected_values
        assert list(d.items()) == expected_items

        assert list(d.keys(2)) == expected_keys * 2
        assert list(d.values(2)) == expected_values * 2
        assert list(d.items(2)) == expected_items * 2


class _MutableMultiDictTests:
    storage_class: t.Type["ds.MultiDict"]

    def test_pickle(self):
        cls = self.storage_class

        def create_instance(module=None):
            if module is None:
                d = cls()
            else:
                old = cls.__module__
                cls.__module__ = module
                d = cls()
                cls.__module__ = old
            d.setlist(b"foo", [1, 2, 3, 4])
            d.setlist(b"bar", b"foo bar baz".split())
            return d

        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            d = create_instance()
            s = pickle.dumps(d, protocol)
            ud = pickle.loads(s)
            assert type(ud) == type(d)
            assert ud == d
            alternative = pickle.dumps(create_instance("werkzeug"), protocol)
            assert pickle.loads(alternative) == d
            ud[b"newkey"] = b"bla"
            assert ud != d

    def test_multidict_dict_interop(self):
        # https://github.com/pallets/werkzeug/pull/2043
        md = self.storage_class([("a", 1), ("a", 2)])
        assert dict(md)["a"] != [1, 2]
        assert dict(md)["a"] == 1
        assert dict(md) == {**md} == {"a": 1}

    def test_basic_interface(self):
        md = self.storage_class()
        assert isinstance(md, dict)

        mapping = [
            ("a", 1),
            ("b", 2),
            ("a", 2),
            ("d", 3),
            ("a", 1),
            ("a", 3),
            ("d", 4),
            ("c", 3),
        ]
        md = self.storage_class(mapping)

        # simple getitem gives the first value
        assert md["a"] == 1
        assert md["c"] == 3
        with pytest.raises(KeyError):
            md["e"]
        assert md.get("a") == 1

        # list getitem
        assert md.getlist("a") == [1, 2, 1, 3]
        assert md.getlist("d") == [3, 4]
        # do not raise if key not found
        assert md.getlist("x") == []

        # simple setitem overwrites all values
        md["a"] = 42
        assert md.getlist("a") == [42]

        # list setitem
        md.setlist("a", [1, 2, 3])
        assert md["a"] == 1
        assert md.getlist("a") == [1, 2, 3]

        # verify that it does not change original lists
        l1 = [1, 2, 3]
        md.setlist("a", l1)
        del l1[:]
        assert md["a"] == 1

        # setdefault, setlistdefault
        assert md.setdefault("u", 23) == 23
        assert md.getlist("u") == [23]
        del md["u"]

        md.setlist("u", [-1, -2])

        # delitem
        del md["u"]
        with pytest.raises(KeyError):
            md["u"]
        del md["d"]
        assert md.getlist("d") == []

        # keys, values, items, lists
        assert list(sorted(md.keys())) == ["a", "b", "c"]
        assert list(sorted(md.keys())) == ["a", "b", "c"]

        assert list(sorted(md.values())) == [1, 2, 3]
        assert list(sorted(md.values())) == [1, 2, 3]

        assert list(sorted(md.items())) == [("a", 1), ("b", 2), ("c", 3)]
        assert list(sorted(md.items(multi=True))) == [
            ("a", 1),
            ("a", 2),
            ("a", 3),
            ("b", 2),
            ("c", 3),
        ]
        assert list(sorted(md.items())) == [("a", 1), ("b", 2), ("c", 3)]
        assert list(sorted(md.items(multi=True))) == [
            ("a", 1),
            ("a", 2),
            ("a", 3),
            ("b", 2),
            ("c", 3),
        ]

        assert list(sorted(md.lists())) == [("a", [1, 2, 3]), ("b", [2]), ("c", [3])]
        assert list(sorted(md.lists())) == [("a", [1, 2, 3]), ("b", [2]), ("c", [3])]

        # copy method
        c = md.copy()
        assert c["a"] == 1
        assert c.getlist("a") == [1, 2, 3]

        # copy method 2
        c = copy(md)
        assert c["a"] == 1
        assert c.getlist("a") == [1, 2, 3]

        # deepcopy method
        c = md.deepcopy()
        assert c["a"] == 1
        assert c.getlist("a") == [1, 2, 3]

        # deepcopy method 2
        c = deepcopy(md)
        assert c["a"] == 1
        assert c.getlist("a") == [1, 2, 3]

        # update with a multidict
        od = self.storage_class([("a", 4), ("a", 5), ("y", 0)])
        md.update(od)
        assert md.getlist("a") == [1, 2, 3, 4, 5]
        assert md.getlist("y") == [0]

        # update with a regular dict
        md = c
        od = {"a": 4, "y": 0}
        md.update(od)
        assert md.getlist("a") == [1, 2, 3, 4]
        assert md.getlist("y") == [0]

        # pop, poplist, popitem, popitemlist
        assert md.pop("y") == 0
        assert "y" not in md
        assert md.poplist("a") == [1, 2, 3, 4]
        assert "a" not in md
        assert md.poplist("missing") == []

        # remaining: b=2, c=3
        popped = md.popitem()
        assert popped in [("b", 2), ("c", 3)]
        popped = md.popitemlist()
        assert popped in [("b", [2]), ("c", [3])]

        # type conversion
        md = self.storage_class({"a": "4", "b": ["2", "3"]})
        assert md.get("a", type=int) == 4
        assert md.getlist("b", type=int) == [2, 3]

        # repr
        md = self.storage_class([("a", 1), ("a", 2), ("b", 3)])
        assert "('a', 1)" in repr(md)
        assert "('a', 2)" in repr(md)
        assert "('b', 3)" in repr(md)

        # add and getlist
        md.add("c", "42")
        md.add("c", "23")
        assert md.getlist("c") == ["42", "23"]
        md.add("c", "blah")
        assert md.getlist("c", type=int) == [42, 23]

        # setdefault
        md = self.storage_class()
        md.setdefault("x", []).append(42)
        md.setdefault("x", []).append(23)
        assert md["x"] == [42, 23]

        # to dict
        md = self.storage_class()
        md["foo"] = 42
        md.add("bar", 1)
        md.add("bar", 2)
        assert md.to_dict() == {"foo": 42, "bar": 1}
        assert md.to_dict(flat=False) == {"foo": [42], "bar": [1, 2]}

        # popitem from empty dict
        with pytest.raises(KeyError):
            self.storage_class().popitem()

        with pytest.raises(KeyError):
            self.storage_class().popitemlist()

        # key errors are of a special type
        with pytest.raises(BadRequestKeyError):
            self.storage_class()[42]

        # setlist works
        md = self.storage_class()
        md["foo"] = 42
        md.setlist("foo", [1, 2])
        assert md.getlist("foo") == [1, 2]


class _ImmutableDictTests:
    storage_class: t.Type[dict]

    def test_follows_dict_interface(self):
        cls = self.storage_class

        data = {"foo": 1, "bar": 2, "baz": 3}
        d = cls(data)

        assert d["foo"] == 1
        assert d["bar"] == 2
        assert d["baz"] == 3
        assert sorted(d.keys()) == ["bar", "baz", "foo"]
        assert "foo" in d
        assert "foox" not in d
        assert len(d) == 3

    def test_copies_are_mutable(self):
        cls = self.storage_class
        immutable = cls({"a": 1})
        with pytest.raises(TypeError):
            immutable.pop("a")

        mutable = immutable.copy()
        mutable.pop("a")
        assert "a" in immutable
        assert mutable is not immutable
        assert copy(immutable) is immutable

    def test_dict_is_hashable(self):
        cls = self.storage_class
        immutable = cls({"a": 1, "b": 2})
        immutable2 = cls({"a": 2, "b": 2})
        x = {immutable}
        assert immutable in x
        assert immutable2 not in x
        x.discard(immutable)
        assert immutable not in x
        assert immutable2 not in x
        x.add(immutable2)
        assert immutable not in x
        assert immutable2 in x
        x.add(immutable)
        assert immutable in x
        assert immutable2 in x


class TestImmutableTypeConversionDict(_ImmutableDictTests):
    storage_class = ds.ImmutableTypeConversionDict


class TestImmutableMultiDict(_ImmutableDictTests):
    storage_class = ds.ImmutableMultiDict

    def test_multidict_is_hashable(self):
        cls = self.storage_class
        immutable = cls({"a": [1, 2], "b": 2})
        immutable2 = cls({"a": [1], "b": 2})
        x = {immutable}
        assert immutable in x
        assert immutable2 not in x
        x.discard(immutable)
        assert immutable not in x
        assert immutable2 not in x
        x.add(immutable2)
        assert immutable not in x
        assert immutable2 in x
        x.add(immutable)
        assert immutable in x
        assert immutable2 in x


class TestImmutableDict(_ImmutableDictTests):
    storage_class = ds.ImmutableDict


class TestImmutableOrderedMultiDict(_ImmutableDictTests):
    storage_class = ds.ImmutableOrderedMultiDict

    def test_ordered_multidict_is_hashable(self):
        a = self.storage_class([("a", 1), ("b", 1), ("a", 2)])
        b = self.storage_class([("a", 1), ("a", 2), ("b", 1)])
        assert hash(a) != hash(b)


class TestMultiDict(_MutableMultiDictTests):
    storage_class = ds.MultiDict

    def test_multidict_pop(self):
        def make_d():
            return self.storage_class({"foo": [1, 2, 3, 4]})

        d = make_d()
        assert d.pop("foo") == 1
        assert not d
        d = make_d()
        assert d.pop("foo", 32) == 1
        assert not d
        d = make_d()
        assert d.pop("foos", 32) == 32
        assert d

        with pytest.raises(KeyError):
            d.pop("foos")

    def test_multidict_pop_raise_badrequestkeyerror_for_empty_list_value(self):
        mapping = [("a", "b"), ("a", "c")]
        md = self.storage_class(mapping)

        md.setlistdefault("empty", [])

        with pytest.raises(KeyError):
            md.pop("empty")

    def test_multidict_popitem_raise_badrequestkeyerror_for_empty_list_value(self):
        mapping = []
        md = self.storage_class(mapping)

        md.setlistdefault("empty", [])

        with pytest.raises(BadRequestKeyError):
            md.popitem()

    def test_setlistdefault(self):
        md = self.storage_class()
        assert md.setlistdefault("u", [-1, -2]) == [-1, -2]
        assert md.getlist("u") == [-1, -2]
        assert md["u"] == -1

    def test_iter_interfaces(self):
        mapping = [
            ("a", 1),
            ("b", 2),
            ("a", 2),
            ("d", 3),
            ("a", 1),
            ("a", 3),
            ("d", 4),
            ("c", 3),
        ]
        md = self.storage_class(mapping)
        assert list(zip(md.keys(), md.listvalues())) == list(md.lists())
        assert list(zip(md, md.listvalues())) == list(md.lists())
        assert list(zip(md.keys(), md.listvalues())) == list(md.lists())

    def test_getitem_raise_badrequestkeyerror_for_empty_list_value(self):
        mapping = [("a", "b"), ("a", "c")]
        md = self.storage_class(mapping)

        md.setlistdefault("empty", [])

        with pytest.raises(KeyError):
            md["empty"]


class TestOrderedMultiDict(_MutableMultiDictTests):
    storage_class = ds.OrderedMultiDict

    def test_ordered_interface(self):
        cls = self.storage_class

        d = cls()
        assert not d
        d.add("foo", "bar")
        assert len(d) == 1
        d.add("foo", "baz")
        assert len(d) == 1
        assert list(d.items()) == [("foo", "bar")]
        assert list(d) == ["foo"]
        assert list(d.items(multi=True)) == [("foo", "bar"), ("foo", "baz")]
        del d["foo"]
        assert not d
        assert len(d) == 0
        assert list(d) == []

        d.update([("foo", 1), ("foo", 2), ("bar", 42)])
        d.add("foo", 3)
        assert d.getlist("foo") == [1, 2, 3]
        assert d.getlist("bar") == [42]
        assert list(d.items()) == [("foo", 1), ("bar", 42)]

        expected = ["foo", "bar"]

        assert list(d.keys()) == expected
        assert list(d) == expected
        assert list(d.keys()) == expected

        assert list(d.items(multi=True)) == [
            ("foo", 1),
            ("foo", 2),
            ("bar", 42),
            ("foo", 3),
        ]
        assert len(d) == 2

        assert d.pop("foo") == 1
        assert d.pop("blafasel", None) is None
        assert d.pop("blafasel", 42) == 42
        assert len(d) == 1
        assert d.poplist("bar") == [42]
        assert not d

        assert d.get("missingkey") is None

        d.add("foo", 42)
        d.add("foo", 23)
        d.add("bar", 2)
        d.add("foo", 42)
        assert d == ds.MultiDict(d)
        id = self.storage_class(d)
        assert d == id
        d.add("foo", 2)
        assert d != id

        d.update({"blah": [1, 2, 3]})
        assert d["blah"] == 1
        assert d.getlist("blah") == [1, 2, 3]

        # setlist works
        d = self.storage_class()
        d["foo"] = 42
        d.setlist("foo", [1, 2])
        assert d.getlist("foo") == [1, 2]
        with pytest.raises(BadRequestKeyError):
            d.pop("missing")

        with pytest.raises(BadRequestKeyError):
            d["missing"]

        # popping
        d = self.storage_class()
        d.add("foo", 23)
        d.add("foo", 42)
        d.add("foo", 1)
        assert d.popitem() == ("foo", 23)
        with pytest.raises(BadRequestKeyError):
            d.popitem()
        assert not d

        d.add("foo", 23)
        d.add("foo", 42)
        d.add("foo", 1)
        assert d.popitemlist() == ("foo", [23, 42, 1])

        with pytest.raises(BadRequestKeyError):
            d.popitemlist()

        # Unhashable
        d = self.storage_class()
        d.add("foo", 23)
        pytest.raises(TypeError, hash, d)

    def test_iterables(self):
        a = ds.MultiDict((("key_a", "value_a"),))
        b = ds.MultiDict((("key_b", "value_b"),))
        ab = ds.CombinedMultiDict((a, b))

        assert sorted(ab.lists()) == [("key_a", ["value_a"]), ("key_b", ["value_b"])]
        assert sorted(ab.listvalues()) == [["value_a"], ["value_b"]]
        assert sorted(ab.keys()) == ["key_a", "key_b"]

        assert sorted(ab.lists()) == [("key_a", ["value_a"]), ("key_b", ["value_b"])]
        assert sorted(ab.listvalues()) == [["value_a"], ["value_b"]]
        assert sorted(ab.keys()) == ["key_a", "key_b"]

    def test_get_description(self):
        data = ds.OrderedMultiDict()

        with pytest.raises(BadRequestKeyError) as exc_info:
            data["baz"]

        assert "baz" not in exc_info.value.get_description()
        exc_info.value.show_exception = True
        assert "baz" in exc_info.value.get_description()

        with pytest.raises(BadRequestKeyError) as exc_info:
            data.pop("baz")

        exc_info.value.show_exception = True
        assert "baz" in exc_info.value.get_description()
        exc_info.value.args = ()
        assert "baz" not in exc_info.value.get_description()


class TestTypeConversionDict:
    storage_class = ds.TypeConversionDict

    def test_value_conversion(self):
        d = self.storage_class(foo="1")
        assert d.get("foo", type=int) == 1

    def test_return_default_when_conversion_is_not_possible(self):
        d = self.storage_class(foo="bar")
        assert d.get("foo", default=-1, type=int) == -1

    def test_propagate_exceptions_in_conversion(self):
        d = self.storage_class(foo="bar")
        switch = {"a": 1}
        with pytest.raises(KeyError):
            d.get("foo", type=lambda x: switch[x])


class TestCombinedMultiDict:
    storage_class = ds.CombinedMultiDict

    def test_basic_interface(self):
        d1 = ds.MultiDict([("foo", "1")])
        d2 = ds.MultiDict([("bar", "2"), ("bar", "3")])
        d = self.storage_class([d1, d2])

        # lookup
        assert d["foo"] == "1"
        assert d["bar"] == "2"
        assert d.getlist("bar") == ["2", "3"]

        assert sorted(d.items()) == [("bar", "2"), ("foo", "1")]
        assert sorted(d.items(multi=True)) == [("bar", "2"), ("bar", "3"), ("foo", "1")]
        assert "missingkey" not in d
        assert "foo" in d

        # type lookup
        assert d.get("foo", type=int) == 1
        assert d.getlist("bar", type=int) == [2, 3]

        # get key errors for missing stuff
        with pytest.raises(KeyError):
            d["missing"]

        # make sure that they are immutable
        with pytest.raises(TypeError):
            d["foo"] = "blub"

        # copies are mutable
        d = d.copy()
        d["foo"] = "blub"

        # make sure lists merges
        md1 = ds.MultiDict((("foo", "bar"),))
        md2 = ds.MultiDict((("foo", "blafasel"),))
        x = self.storage_class((md1, md2))
        assert list(x.lists()) == [("foo", ["bar", "blafasel"])]

    def test_length(self):
        d1 = ds.MultiDict([("foo", "1")])
        d2 = ds.MultiDict([("bar", "2")])
        assert len(d1) == len(d2) == 1
        d = self.storage_class([d1, d2])
        assert len(d) == 2
        d1.clear()
        assert len(d1) == 0
        assert len(d) == 1


class TestHeaders:
    storage_class = ds.Headers

    def test_basic_interface(self):
        headers = self.storage_class()
        headers.add("Content-Type", "text/plain")
        headers.add("X-Foo", "bar")
        assert "x-Foo" in headers
        assert "Content-type" in headers

        headers["Content-Type"] = "foo/bar"
        assert headers["Content-Type"] == "foo/bar"
        assert len(headers.getlist("Content-Type")) == 1

        # list conversion
        assert headers.to_wsgi_list() == [("Content-Type", "foo/bar"), ("X-Foo", "bar")]
        assert str(headers) == "Content-Type: foo/bar\r\nX-Foo: bar\r\n\r\n"
        assert str(self.storage_class()) == "\r\n"

        # extended add
        headers.add("Content-Disposition", "attachment", filename="foo")
        assert headers["Content-Disposition"] == "attachment; filename=foo"

        headers.add("x", "y", z='"')
        assert headers["x"] == r'y; z="\""'

    def test_defaults_and_conversion(self):
        # defaults
        headers = self.storage_class(
            [
                ("Content-Type", "text/plain"),
                ("X-Foo", "bar"),
                ("X-Bar", "1"),
                ("X-Bar", "2"),
            ]
        )
        assert headers.getlist("x-bar") == ["1", "2"]
        assert headers.get("x-Bar") == "1"
        assert headers.get("Content-Type") == "text/plain"

        assert headers.setdefault("X-Foo", "nope") == "bar"
        assert headers.setdefault("X-Bar", "nope") == "1"
        assert headers.setdefault("X-Baz", "quux") == "quux"
        assert headers.setdefault("X-Baz", "nope") == "quux"
        headers.pop("X-Baz")

        # type conversion
        assert headers.get("x-bar", type=int) == 1
        assert headers.getlist("x-bar", type=int) == [1, 2]

        # list like operations
        assert headers[0] == ("Content-Type", "text/plain")
        assert headers[:1] == self.storage_class([("Content-Type", "text/plain")])
        del headers[:2]
        del headers[-1]
        assert headers == self.storage_class([("X-Bar", "1")])

    def test_copying(self):
        a = self.storage_class([("foo", "bar")])
        b = a.copy()
        a.add("foo", "baz")
        assert a.getlist("foo") == ["bar", "baz"]
        assert b.getlist("foo") == ["bar"]

    def test_popping(self):
        headers = self.storage_class([("a", 1)])
        assert headers.pop("a") == 1
        assert headers.pop("b", 2) == 2

        with pytest.raises(KeyError):
            headers.pop("c")

    def test_set_arguments(self):
        a = self.storage_class()
        a.set("Content-Disposition", "useless")
        a.set("Content-Disposition", "attachment", filename="foo")
        assert a["Content-Disposition"] == "attachment; filename=foo"

    def test_reject_newlines(self):
        h = self.storage_class()

        for variation in "foo\nbar", "foo\r\nbar", "foo\rbar":
            with pytest.raises(ValueError):
                h["foo"] = variation
            with pytest.raises(ValueError):
                h.add("foo", variation)
            with pytest.raises(ValueError):
                h.add("foo", "test", option=variation)
            with pytest.raises(ValueError):
                h.set("foo", variation)
            with pytest.raises(ValueError):
                h.set("foo", "test", option=variation)

    def test_slicing(self):
        # there's nothing wrong with these being native strings
        # Headers doesn't care about the data types
        h = self.storage_class()
        h.set("X-Foo-Poo", "bleh")
        h.set("Content-Type", "application/whocares")
        h.set("X-Forwarded-For", "192.168.0.123")
        h[:] = [(k, v) for k, v in h if k.startswith("X-")]
        assert list(h) == [("X-Foo-Poo", "bleh"), ("X-Forwarded-For", "192.168.0.123")]

    def test_bytes_operations(self):
        h = self.storage_class()
        h.set("X-Foo-Poo", "bleh")
        h.set("X-Whoops", b"\xff")
        h.set(b"X-Bytes", b"something")

        assert h.get("x-foo-poo", as_bytes=True) == b"bleh"
        assert h.get("x-whoops", as_bytes=True) == b"\xff"
        assert h.get("x-bytes") == "something"

    def test_extend(self):
        h = self.storage_class([("a", "0"), ("b", "1"), ("c", "2")])
        h.extend(ds.Headers([("a", "3"), ("a", "4")]))
        assert h.getlist("a") == ["0", "3", "4"]
        h.extend(b=["5", "6"])
        assert h.getlist("b") == ["1", "5", "6"]
        h.extend({"c": "7", "d": ["8", "9"]}, c="10")
        assert h.getlist("c") == ["2", "7", "10"]
        assert h.getlist("d") == ["8", "9"]

        with pytest.raises(TypeError):
            h.extend({"x": "x"}, {"x": "x"})

    def test_update(self):
        h = self.storage_class([("a", "0"), ("b", "1"), ("c", "2")])
        h.update(ds.Headers([("a", "3"), ("a", "4")]))
        assert h.getlist("a") == ["3", "4"]
        h.update(b=["5", "6"])
        assert h.getlist("b") == ["5", "6"]
        h.update({"c": "7", "d": ["8", "9"]})
        assert h.getlist("c") == ["7"]
        assert h.getlist("d") == ["8", "9"]
        h.update({"c": "10"}, c="11")
        assert h.getlist("c") == ["11"]

        with pytest.raises(TypeError):
            h.extend({"x": "x"}, {"x": "x"})

    def test_setlist(self):
        h = self.storage_class([("a", "0"), ("b", "1"), ("c", "2")])
        h.setlist("b", ["3", "4"])
        assert h[1] == ("b", "3")
        assert h[-1] == ("b", "4")
        h.setlist("b", [])
        assert "b" not in h
        h.setlist("d", ["5"])
        assert h["d"] == "5"

    def test_setlistdefault(self):
        h = self.storage_class([("a", "0"), ("b", "1"), ("c", "2")])
        assert h.setlistdefault("a", ["3"]) == ["0"]
        assert h.setlistdefault("d", ["4", "5"]) == ["4", "5"]

    def test_to_wsgi_list(self):
        h = self.storage_class()
        h.set("Key", "Value")
        for key, value in h.to_wsgi_list():
            assert key == "Key"
            assert value == "Value"

    def test_to_wsgi_list_bytes(self):
        h = self.storage_class()
        h.set(b"Key", b"Value")
        for key, value in h.to_wsgi_list():
            assert key == "Key"
            assert value == "Value"

    def test_equality(self):
        # test equality, given keys are case insensitive
        h1 = self.storage_class()
        h1.add("X-Foo", "foo")
        h1.add("X-Bar", "bah")
        h1.add("X-Bar", "humbug")

        h2 = self.storage_class()
        h2.add("x-foo", "foo")
        h2.add("x-bar", "bah")
        h2.add("x-bar", "humbug")

        assert h1 == h2


class TestEnvironHeaders:
    storage_class = ds.EnvironHeaders

    def test_basic_interface(self):
        # this happens in multiple WSGI servers because they
        # use a vary naive way to convert the headers;
        broken_env = {
            "HTTP_CONTENT_TYPE": "text/html",
            "CONTENT_TYPE": "text/html",
            "HTTP_CONTENT_LENGTH": "0",
            "CONTENT_LENGTH": "0",
            "HTTP_ACCEPT": "*",
            "wsgi.version": (1, 0),
        }
        headers = self.storage_class(broken_env)
        assert headers
        assert len(headers) == 3
        assert sorted(headers) == [
            ("Accept", "*"),
            ("Content-Length", "0"),
            ("Content-Type", "text/html"),
        ]
        assert not self.storage_class({"wsgi.version": (1, 0)})
        assert len(self.storage_class({"wsgi.version": (1, 0)})) == 0
        assert 42 not in headers

    def test_skip_empty_special_vars(self):
        env = {"HTTP_X_FOO": "42", "CONTENT_TYPE": "", "CONTENT_LENGTH": ""}
        headers = self.storage_class(env)
        assert dict(headers) == {"X-Foo": "42"}

        env = {"HTTP_X_FOO": "42", "CONTENT_TYPE": "", "CONTENT_LENGTH": "0"}
        headers = self.storage_class(env)
        assert dict(headers) == {"X-Foo": "42", "Content-Length": "0"}

    def test_return_type_is_str(self):
        headers = self.storage_class({"HTTP_FOO": "\xe2\x9c\x93"})
        assert headers["Foo"] == "\xe2\x9c\x93"
        assert next(iter(headers)) == ("Foo", "\xe2\x9c\x93")

    def test_bytes_operations(self):
        foo_val = "\xff"
        h = self.storage_class({"HTTP_X_FOO": foo_val})

        assert h.get("x-foo", as_bytes=True) == b"\xff"
        assert h.get("x-foo") == "\xff"


class TestHeaderSet:
    storage_class = ds.HeaderSet

    def test_basic_interface(self):
        hs = self.storage_class()
        hs.add("foo")
        hs.add("bar")
        assert "Bar" in hs
        assert hs.find("foo") == 0
        assert hs.find("BAR") == 1
        assert hs.find("baz") < 0
        hs.discard("missing")
        hs.discard("foo")
        assert hs.find("foo") < 0
        assert hs.find("bar") == 0

        with pytest.raises(IndexError):
            hs.index("missing")

        assert hs.index("bar") == 0
        assert hs
        hs.clear()
        assert not hs


class TestImmutableList:
    storage_class = ds.ImmutableList

    def test_list_hashable(self):
        data = (1, 2, 3, 4)
        store = self.storage_class(data)
        assert hash(data) == hash(store)
        assert data != store


def make_call_asserter(func=None):
    """Utility to assert a certain number of function calls.

    :param func: Additional callback for each function call.

    .. code-block:: python
        assert_calls, func = make_call_asserter()
        with assert_calls(2):
            func()
            func()
    """
    calls = [0]

    @contextmanager
    def asserter(count, msg=None):
        calls[0] = 0
        yield
        assert calls[0] == count

    def wrapped(*args, **kwargs):
        calls[0] += 1
        if func is not None:
            return func(*args, **kwargs)

    return asserter, wrapped


class TestCallbackDict:
    storage_class = ds.CallbackDict

    def test_callback_dict_reads(self):
        assert_calls, func = make_call_asserter()
        initial = {"a": "foo", "b": "bar"}
        dct = self.storage_class(initial=initial, on_update=func)
        with assert_calls(0, "callback triggered by read-only method"):
            # read-only methods
            dct["a"]
            dct.get("a")
            pytest.raises(KeyError, lambda: dct["x"])
            assert "a" in dct
            list(iter(dct))
            dct.copy()
        with assert_calls(0, "callback triggered without modification"):
            # methods that may write but don't
            dct.pop("z", None)
            dct.setdefault("a")

    def test_callback_dict_writes(self):
        assert_calls, func = make_call_asserter()
        initial = {"a": "foo", "b": "bar"}
        dct = self.storage_class(initial=initial, on_update=func)
        with assert_calls(8, "callback not triggered by write method"):
            # always-write methods
            dct["z"] = 123
            dct["z"] = 123  # must trigger again
            del dct["z"]
            dct.pop("b", None)
            dct.setdefault("x")
            dct.popitem()
            dct.update([])
            dct.clear()
        with assert_calls(0, "callback triggered by failed del"):
            pytest.raises(KeyError, lambda: dct.__delitem__("x"))
        with assert_calls(0, "callback triggered by failed pop"):
            pytest.raises(KeyError, lambda: dct.pop("x"))


class TestCacheControl:
    def test_repr(self):
        cc = ds.RequestCacheControl([("max-age", "0"), ("private", "True")])
        assert repr(cc) == "<RequestCacheControl max-age='0' private='True'>"

    def test_set_none(self):
        cc = ds.ResponseCacheControl([("max-age", "0")])
        assert cc.no_cache is None
        cc.no_cache = None
        assert cc.no_cache is None


class TestContentSecurityPolicy:
    def test_construct(self):
        csp = ds.ContentSecurityPolicy([("font-src", "'self'"), ("media-src", "*")])
        assert csp.font_src == "'self'"
        assert csp.media_src == "*"
        policies = [policy.strip() for policy in csp.to_header().split(";")]
        assert "font-src 'self'" in policies
        assert "media-src *" in policies

    def test_properties(self):
        csp = ds.ContentSecurityPolicy()
        csp.default_src = "* 'self' quart.com"
        csp.img_src = "'none'"
        policies = [policy.strip() for policy in csp.to_header().split(";")]
        assert "default-src * 'self' quart.com" in policies
        assert "img-src 'none'" in policies


class TestAccept:
    storage_class = ds.Accept

    def test_accept_basic(self):
        accept = self.storage_class(
            [("tinker", 0), ("tailor", 0.333), ("soldier", 0.667), ("sailor", 1)]
        )
        # check __getitem__ on indices
        assert accept[3] == ("tinker", 0)
        assert accept[2] == ("tailor", 0.333)
        assert accept[1] == ("soldier", 0.667)
        assert accept[0], ("sailor", 1)
        # check __getitem__ on string
        assert accept["tinker"] == 0
        assert accept["tailor"] == 0.333
        assert accept["soldier"] == 0.667
        assert accept["sailor"] == 1
        assert accept["spy"] == 0
        # check quality method
        assert accept.quality("tinker") == 0
        assert accept.quality("tailor") == 0.333
        assert accept.quality("soldier") == 0.667
        assert accept.quality("sailor") == 1
        assert accept.quality("spy") == 0
        # check __contains__
        assert "sailor" in accept
        assert "spy" not in accept
        # check index method
        assert accept.index("tinker") == 3
        assert accept.index("tailor") == 2
        assert accept.index("soldier") == 1
        assert accept.index("sailor") == 0
        with pytest.raises(ValueError):
            accept.index("spy")
        # check find method
        assert accept.find("tinker") == 3
        assert accept.find("tailor") == 2
        assert accept.find("soldier") == 1
        assert accept.find("sailor") == 0
        assert accept.find("spy") == -1
        # check to_header method
        assert accept.to_header() == "sailor,soldier;q=0.667,tailor;q=0.333,tinker;q=0"
        # check best_match method
        assert (
            accept.best_match(["tinker", "tailor", "soldier", "sailor"], default=None)
            == "sailor"
        )
        assert (
            accept.best_match(["tinker", "tailor", "soldier"], default=None)
            == "soldier"
        )
        assert accept.best_match(["tinker", "tailor"], default=None) == "tailor"
        assert accept.best_match(["tinker"], default=None) is None
        assert accept.best_match(["tinker"], default="x") == "x"

    def test_accept_wildcard(self):
        accept = self.storage_class([("*", 0), ("asterisk", 1)])
        assert "*" in accept
        assert accept.best_match(["asterisk", "star"], default=None) == "asterisk"
        assert accept.best_match(["star"], default=None) is None

    def test_accept_keep_order(self):
        accept = self.storage_class([("*", 1)])
        assert accept.best_match(["alice", "bob"]) == "alice"
        assert accept.best_match(["bob", "alice"]) == "bob"
        accept = self.storage_class([("alice", 1), ("bob", 1)])
        assert accept.best_match(["alice", "bob"]) == "alice"
        assert accept.best_match(["bob", "alice"]) == "bob"

    def test_accept_wildcard_specificity(self):
        accept = self.storage_class([("asterisk", 0), ("star", 0.5), ("*", 1)])
        assert accept.best_match(["star", "asterisk"], default=None) == "star"
        assert accept.best_match(["asterisk", "star"], default=None) == "star"
        assert accept.best_match(["asterisk", "times"], default=None) == "times"
        assert accept.best_match(["asterisk"], default=None) is None

    def test_accept_equal_quality(self):
        accept = self.storage_class([("a", 1), ("b", 1)])
        assert accept.best == "a"


class TestMIMEAccept:
    @pytest.mark.parametrize(
        ("values", "matches", "default", "expect"),
        [
            ([("text/*", 1)], ["text/html"], None, "text/html"),
            ([("text/*", 1)], ["image/png"], "text/plain", "text/plain"),
            ([("text/*", 1)], ["image/png"], None, None),
            (
                [("*/*", 1), ("text/html", 1)],
                ["image/png", "text/html"],
                None,
                "text/html",
            ),
            (
                [("*/*", 1), ("text/html", 1)],
                ["image/png", "text/plain"],
                None,
                "image/png",
            ),
            (
                [("*/*", 1), ("text/html", 1), ("image/*", 1)],
                ["image/png", "text/html"],
                None,
                "text/html",
            ),
            (
                [("*/*", 1), ("text/html", 1), ("image/*", 1)],
                ["text/plain", "image/png"],
                None,
                "image/png",
            ),
            (
                [("text/html", 1), ("text/html; level=1", 1)],
                ["text/html;level=1"],
                None,
                "text/html;level=1",
            ),
        ],
    )
    def test_mime_accept(self, values, matches, default, expect):
        accept = ds.MIMEAccept(values)
        match = accept.best_match(matches, default=default)
        assert match == expect


class TestLanguageAccept:
    @pytest.mark.parametrize(
        ("values", "matches", "default", "expect"),
        (
            ([("en-us", 1)], ["en"], None, "en"),
            ([("en", 1)], ["en_US"], None, "en_US"),
            ([("en-GB", 1)], ["en-US"], None, None),
            ([("de_AT", 1), ("de", 0.9)], ["en"], None, None),
            ([("de_AT", 1), ("de", 0.9), ("en-US", 0.8)], ["de", "en"], None, "de"),
            ([("de_AT", 0.9), ("en-US", 1)], ["en"], None, "en"),
            ([("en-us", 1)], ["en-us"], None, "en-us"),
            ([("en-us", 1)], ["en-us", "en"], None, "en-us"),
            ([("en-GB", 1)], ["en-US", "en"], "en-US", "en"),
            ([("de_AT", 1)], ["en-US", "en"], "en-US", "en-US"),
            ([("aus-EN", 1)], ["aus"], None, "aus"),
            ([("aus", 1)], ["aus-EN"], None, "aus-EN"),
        ),
    )
    def test_best_match_fallback(self, values, matches, default, expect):
        accept = ds.LanguageAccept(values)
        best = accept.best_match(matches, default=default)
        assert best == expect


class TestFileStorage:
    storage_class = ds.FileStorage

    def test_mimetype_always_lowercase(self):
        file_storage = self.storage_class(content_type="APPLICATION/JSON")
        assert file_storage.mimetype == "application/json"

    @pytest.mark.parametrize("data", [io.StringIO("one\ntwo"), io.BytesIO(b"one\ntwo")])
    def test_bytes_proper_sentinel(self, data):
        # iterate over new lines and don't enter an infinite loop
        storage = self.storage_class(data)
        idx = -1

        for idx, _line in enumerate(storage):
            assert idx < 2

        assert idx == 1

    @pytest.mark.parametrize("stream", (tempfile.SpooledTemporaryFile, io.BytesIO))
    def test_proxy_can_access_stream_attrs(self, stream):
        """``SpooledTemporaryFile`` doesn't implement some of
        ``IOBase``. Ensure that ``FileStorage`` can still access the
        attributes from the backing file object.

        https://github.com/pallets/werkzeug/issues/1344
        https://github.com/python/cpython/pull/3249
        """
        file_storage = self.storage_class(stream=stream())

        for name in ("fileno", "writable", "readable", "seekable"):
            assert hasattr(file_storage, name)

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    def test_save_to_pathlib_dst(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("test")
        storage = self.storage_class(src.open("rb"))
        dst = tmp_path / "dst.txt"
        storage.save(dst)
        assert dst.read_text() == "test"

    def test_save_to_bytes_io(self):
        storage = self.storage_class(io.BytesIO(b"one\ntwo"))
        dst = io.BytesIO()
        storage.save(dst)
        assert dst.getvalue() == b"one\ntwo"

    def test_save_to_file(self, tmp_path):
        path = tmp_path / "file.data"
        storage = self.storage_class(io.BytesIO(b"one\ntwo"))
        with path.open("wb") as dst:
            storage.save(dst)
        with path.open("rb") as src:
            assert src.read() == b"one\ntwo"


@pytest.mark.parametrize("ranges", ([(0, 1), (-5, None)], [(5, None)]))
def test_range_to_header(ranges):
    header = ds.Range("byes", ranges).to_header()
    r = http.parse_range_header(header)
    assert r.ranges == ranges


@pytest.mark.parametrize(
    "ranges", ([(0, 0)], [(None, 1)], [(1, 0)], [(0, 1), (-5, 10)])
)
def test_range_validates_ranges(ranges):
    with pytest.raises(ValueError):
        ds.Range("bytes", ranges)
