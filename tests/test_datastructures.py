# -*- coding: utf-8 -*-
"""
    tests.datastructures
    ~~~~~~~~~~~~~~~~~~~~

    Tests the functionality of the provided Werkzeug
    datastructures.

    Classes prefixed with an underscore are mixins and are not discovered by
    the test runner.

    TODO:

    -   FileMultiDict
    -   Immutable types undertested
    -   Split up dict tests

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement

import pytest
from tests import strict_eq


import pickle
from contextlib import contextmanager
from copy import copy, deepcopy

from werkzeug import datastructures
from werkzeug._compat import iterkeys, itervalues, iteritems, iterlists, \
    iterlistvalues, text_type, PY2
from werkzeug.exceptions import BadRequestKeyError


class TestNativeItermethods(object):

    def test_basic(self):
        @datastructures.native_itermethods(['keys', 'values', 'items'])
        class StupidDict(object):

            def keys(self, multi=1):
                return iter(['a', 'b', 'c'] * multi)

            def values(self, multi=1):
                return iter([1, 2, 3] * multi)

            def items(self, multi=1):
                return iter(zip(iterkeys(self, multi=multi),
                                itervalues(self, multi=multi)))

        d = StupidDict()
        expected_keys = ['a', 'b', 'c']
        expected_values = [1, 2, 3]
        expected_items = list(zip(expected_keys, expected_values))

        assert list(iterkeys(d)) == expected_keys
        assert list(itervalues(d)) == expected_values
        assert list(iteritems(d)) == expected_items

        assert list(iterkeys(d, 2)) == expected_keys * 2
        assert list(itervalues(d, 2)) == expected_values * 2
        assert list(iteritems(d, 2)) == expected_items * 2


class _MutableMultiDictTests(object):
    storage_class = None

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
            d.setlist(b'foo', [1, 2, 3, 4])
            d.setlist(b'bar', b'foo bar baz'.split())
            return d

        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            d = create_instance()
            s = pickle.dumps(d, protocol)
            ud = pickle.loads(s)
            assert type(ud) == type(d)
            assert ud == d
            alternative = pickle.dumps(create_instance('werkzeug'), protocol)
            assert pickle.loads(alternative) == d
            ud[b'newkey'] = b'bla'
            assert ud != d

    def test_basic_interface(self):
        md = self.storage_class()
        assert isinstance(md, dict)

        mapping = [('a', 1), ('b', 2), ('a', 2), ('d', 3),
                   ('a', 1), ('a', 3), ('d', 4), ('c', 3)]
        md = self.storage_class(mapping)

        # simple getitem gives the first value
        assert md['a'] == 1
        assert md['c'] == 3
        with pytest.raises(KeyError):
            md['e']
        assert md.get('a') == 1

        # list getitem
        assert md.getlist('a') == [1, 2, 1, 3]
        assert md.getlist('d') == [3, 4]
        # do not raise if key not found
        assert md.getlist('x') == []

        # simple setitem overwrites all values
        md['a'] = 42
        assert md.getlist('a') == [42]

        # list setitem
        md.setlist('a', [1, 2, 3])
        assert md['a'] == 1
        assert md.getlist('a') == [1, 2, 3]

        # verify that it does not change original lists
        l1 = [1, 2, 3]
        md.setlist('a', l1)
        del l1[:]
        assert md['a'] == 1

        # setdefault, setlistdefault
        assert md.setdefault('u', 23) == 23
        assert md.getlist('u') == [23]
        del md['u']

        md.setlist('u', [-1, -2])

        # delitem
        del md['u']
        with pytest.raises(KeyError):
            md['u']
        del md['d']
        assert md.getlist('d') == []

        # keys, values, items, lists
        assert list(sorted(md.keys())) == ['a', 'b', 'c']
        assert list(sorted(iterkeys(md))) == ['a', 'b', 'c']

        assert list(sorted(itervalues(md))) == [1, 2, 3]
        assert list(sorted(itervalues(md))) == [1, 2, 3]

        assert list(sorted(md.items())) == [('a', 1), ('b', 2), ('c', 3)]
        assert list(sorted(md.items(multi=True))) == \
            [('a', 1), ('a', 2), ('a', 3), ('b', 2), ('c', 3)]
        assert list(sorted(iteritems(md))) == [('a', 1), ('b', 2), ('c', 3)]
        assert list(sorted(iteritems(md, multi=True))) == \
            [('a', 1), ('a', 2), ('a', 3), ('b', 2), ('c', 3)]

        assert list(sorted(md.lists())) == \
            [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]
        assert list(sorted(iterlists(md))) == \
            [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]

        # copy method
        c = md.copy()
        assert c['a'] == 1
        assert c.getlist('a') == [1, 2, 3]

        # copy method 2
        c = copy(md)
        assert c['a'] == 1
        assert c.getlist('a') == [1, 2, 3]

        # deepcopy method
        c = md.deepcopy()
        assert c['a'] == 1
        assert c.getlist('a') == [1, 2, 3]

        # deepcopy method 2
        c = deepcopy(md)
        assert c['a'] == 1
        assert c.getlist('a') == [1, 2, 3]

        # update with a multidict
        od = self.storage_class([('a', 4), ('a', 5), ('y', 0)])
        md.update(od)
        assert md.getlist('a') == [1, 2, 3, 4, 5]
        assert md.getlist('y') == [0]

        # update with a regular dict
        md = c
        od = {'a': 4, 'y': 0}
        md.update(od)
        assert md.getlist('a') == [1, 2, 3, 4]
        assert md.getlist('y') == [0]

        # pop, poplist, popitem, popitemlist
        assert md.pop('y') == 0
        assert 'y' not in md
        assert md.poplist('a') == [1, 2, 3, 4]
        assert 'a' not in md
        assert md.poplist('missing') == []

        # remaining: b=2, c=3
        popped = md.popitem()
        assert popped in [('b', 2), ('c', 3)]
        popped = md.popitemlist()
        assert popped in [('b', [2]), ('c', [3])]

        # type conversion
        md = self.storage_class({'a': '4', 'b': ['2', '3']})
        assert md.get('a', type=int) == 4
        assert md.getlist('b', type=int) == [2, 3]

        # repr
        md = self.storage_class([('a', 1), ('a', 2), ('b', 3)])
        assert "('a', 1)" in repr(md)
        assert "('a', 2)" in repr(md)
        assert "('b', 3)" in repr(md)

        # add and getlist
        md.add('c', '42')
        md.add('c', '23')
        assert md.getlist('c') == ['42', '23']
        md.add('c', 'blah')
        assert md.getlist('c', type=int) == [42, 23]

        # setdefault
        md = self.storage_class()
        md.setdefault('x', []).append(42)
        md.setdefault('x', []).append(23)
        assert md['x'] == [42, 23]

        # to dict
        md = self.storage_class()
        md['foo'] = 42
        md.add('bar', 1)
        md.add('bar', 2)
        assert md.to_dict() == {'foo': 42, 'bar': 1}
        assert md.to_dict(flat=False) == {'foo': [42], 'bar': [1, 2]}

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
        md['foo'] = 42
        md.setlist('foo', [1, 2])
        assert md.getlist('foo') == [1, 2]


class _ImmutableDictTests(object):
    storage_class = None

    def test_follows_dict_interface(self):
        cls = self.storage_class

        data = {'foo': 1, 'bar': 2, 'baz': 3}
        d = cls(data)

        assert d['foo'] == 1
        assert d['bar'] == 2
        assert d['baz'] == 3
        assert sorted(d.keys()) == ['bar', 'baz', 'foo']
        assert 'foo' in d
        assert 'foox' not in d
        assert len(d) == 3

    def test_copies_are_mutable(self):
        cls = self.storage_class
        immutable = cls({'a': 1})
        with pytest.raises(TypeError):
            immutable.pop('a')

        mutable = immutable.copy()
        mutable.pop('a')
        assert 'a' in immutable
        assert mutable is not immutable
        assert copy(immutable) is immutable

    def test_dict_is_hashable(self):
        cls = self.storage_class
        immutable = cls({'a': 1, 'b': 2})
        immutable2 = cls({'a': 2, 'b': 2})
        x = set([immutable])
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
    storage_class = datastructures.ImmutableTypeConversionDict


class TestImmutableMultiDict(_ImmutableDictTests):
    storage_class = datastructures.ImmutableMultiDict

    def test_multidict_is_hashable(self):
        cls = self.storage_class
        immutable = cls({'a': [1, 2], 'b': 2})
        immutable2 = cls({'a': [1], 'b': 2})
        x = set([immutable])
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
    storage_class = datastructures.ImmutableDict


class TestImmutableOrderedMultiDict(_ImmutableDictTests):
    storage_class = datastructures.ImmutableOrderedMultiDict

    def test_ordered_multidict_is_hashable(self):
        a = self.storage_class([('a', 1), ('b', 1), ('a', 2)])
        b = self.storage_class([('a', 1), ('a', 2), ('b', 1)])
        assert hash(a) != hash(b)


class TestMultiDict(_MutableMultiDictTests):
    storage_class = datastructures.MultiDict

    def test_multidict_pop(self):
        make_d = lambda: self.storage_class({'foo': [1, 2, 3, 4]})
        d = make_d()
        assert d.pop('foo') == 1
        assert not d
        d = make_d()
        assert d.pop('foo', 32) == 1
        assert not d
        d = make_d()
        assert d.pop('foos', 32) == 32
        assert d

        with pytest.raises(KeyError):
            d.pop('foos')

    def test_setlistdefault(self):
        md = self.storage_class()
        assert md.setlistdefault('u', [-1, -2]) == [-1, -2]
        assert md.getlist('u') == [-1, -2]
        assert md['u'] == -1

    def test_iter_interfaces(self):
        mapping = [('a', 1), ('b', 2), ('a', 2), ('d', 3),
                   ('a', 1), ('a', 3), ('d', 4), ('c', 3)]
        md = self.storage_class(mapping)
        assert list(zip(md.keys(), md.listvalues())) == list(md.lists())
        assert list(zip(md, iterlistvalues(md))) == list(iterlists(md))
        assert list(zip(iterkeys(md), iterlistvalues(md))) == \
            list(iterlists(md))


class TestOrderedMultiDict(_MutableMultiDictTests):
    storage_class = datastructures.OrderedMultiDict

    def test_ordered_interface(self):
        cls = self.storage_class

        d = cls()
        assert not d
        d.add('foo', 'bar')
        assert len(d) == 1
        d.add('foo', 'baz')
        assert len(d) == 1
        assert list(iteritems(d)) == [('foo', 'bar')]
        assert list(d) == ['foo']
        assert list(iteritems(d, multi=True)) == \
            [('foo', 'bar'), ('foo', 'baz')]
        del d['foo']
        assert not d
        assert len(d) == 0
        assert list(d) == []

        d.update([('foo', 1), ('foo', 2), ('bar', 42)])
        d.add('foo', 3)
        assert d.getlist('foo') == [1, 2, 3]
        assert d.getlist('bar') == [42]
        assert list(iteritems(d)) == [('foo', 1), ('bar', 42)]

        expected = ['foo', 'bar']

        assert list(d.keys()) == expected
        assert list(d) == expected
        assert list(iterkeys(d)) == expected

        assert list(iteritems(d, multi=True)) == \
            [('foo', 1), ('foo', 2), ('bar', 42), ('foo', 3)]
        assert len(d) == 2

        assert d.pop('foo') == 1
        assert d.pop('blafasel', None) is None
        assert d.pop('blafasel', 42) == 42
        assert len(d) == 1
        assert d.poplist('bar') == [42]
        assert not d

        d.get('missingkey') is None

        d.add('foo', 42)
        d.add('foo', 23)
        d.add('bar', 2)
        d.add('foo', 42)
        assert d == datastructures.MultiDict(d)
        id = self.storage_class(d)
        assert d == id
        d.add('foo', 2)
        assert d != id

        d.update({'blah': [1, 2, 3]})
        assert d['blah'] == 1
        assert d.getlist('blah') == [1, 2, 3]

        # setlist works
        d = self.storage_class()
        d['foo'] = 42
        d.setlist('foo', [1, 2])
        assert d.getlist('foo') == [1, 2]

        with pytest.raises(BadRequestKeyError):
            d.pop('missing')
        with pytest.raises(BadRequestKeyError):
            d['missing']

        # popping
        d = self.storage_class()
        d.add('foo', 23)
        d.add('foo', 42)
        d.add('foo', 1)
        assert d.popitem() == ('foo', 23)
        with pytest.raises(BadRequestKeyError):
            d.popitem()
        assert not d

        d.add('foo', 23)
        d.add('foo', 42)
        d.add('foo', 1)
        assert d.popitemlist() == ('foo', [23, 42, 1])

        with pytest.raises(BadRequestKeyError):
            d.popitemlist()

    def test_iterables(self):
        a = datastructures.MultiDict((("key_a", "value_a"),))
        b = datastructures.MultiDict((("key_b", "value_b"),))
        ab = datastructures.CombinedMultiDict((a, b))

        assert sorted(ab.lists()) == [('key_a', ['value_a']), ('key_b', ['value_b'])]
        assert sorted(ab.listvalues()) == [['value_a'], ['value_b']]
        assert sorted(ab.keys()) == ["key_a", "key_b"]

        assert sorted(iterlists(ab)) == [('key_a', ['value_a']), ('key_b', ['value_b'])]
        assert sorted(iterlistvalues(ab)) == [['value_a'], ['value_b']]
        assert sorted(iterkeys(ab)) == ["key_a", "key_b"]


class TestCombinedMultiDict(object):
    storage_class = datastructures.CombinedMultiDict

    def test_basic_interface(self):
        d1 = datastructures.MultiDict([('foo', '1')])
        d2 = datastructures.MultiDict([('bar', '2'), ('bar', '3')])
        d = self.storage_class([d1, d2])

        # lookup
        assert d['foo'] == '1'
        assert d['bar'] == '2'
        assert d.getlist('bar') == ['2', '3']

        assert sorted(d.items()) == [('bar', '2'), ('foo', '1')]
        assert sorted(d.items(multi=True)) == \
            [('bar', '2'), ('bar', '3'), ('foo', '1')]
        assert 'missingkey' not in d
        assert 'foo' in d

        # type lookup
        assert d.get('foo', type=int) == 1
        assert d.getlist('bar', type=int) == [2, 3]

        # get key errors for missing stuff
        with pytest.raises(KeyError):
            d['missing']

        # make sure that they are immutable
        with pytest.raises(TypeError):
            d['foo'] = 'blub'

        # copies are immutable
        d = d.copy()
        with pytest.raises(TypeError):
            d['foo'] = 'blub'

        # make sure lists merges
        md1 = datastructures.MultiDict((("foo", "bar"),))
        md2 = datastructures.MultiDict((("foo", "blafasel"),))
        x = self.storage_class((md1, md2))
        assert list(iterlists(x)) == [('foo', ['bar', 'blafasel'])]

    def test_length(self):
        d1 = datastructures.MultiDict([('foo', '1')])
        d2 = datastructures.MultiDict([('bar', '2')])
        assert len(d1) == len(d2) == 1
        d = self.storage_class([d1, d2])
        assert len(d) == 2
        d1.clear()
        assert len(d1) == 0
        assert len(d) == 1


class TestHeaders(object):
    storage_class = datastructures.Headers

    def test_basic_interface(self):
        headers = self.storage_class()
        headers.add('Content-Type', 'text/plain')
        headers.add('X-Foo', 'bar')
        assert 'x-Foo' in headers
        assert 'Content-type' in headers

        headers['Content-Type'] = 'foo/bar'
        assert headers['Content-Type'] == 'foo/bar'
        assert len(headers.getlist('Content-Type')) == 1

        # list conversion
        assert headers.to_wsgi_list() == [
            ('Content-Type', 'foo/bar'),
            ('X-Foo', 'bar')
        ]
        assert str(headers) == (
            "Content-Type: foo/bar\r\n"
            "X-Foo: bar\r\n"
            "\r\n"
        )
        assert str(self.storage_class()) == "\r\n"

        # extended add
        headers.add('Content-Disposition', 'attachment', filename='foo')
        assert headers['Content-Disposition'] == 'attachment; filename=foo'

        headers.add('x', 'y', z='"')
        assert headers['x'] == r'y; z="\""'

    def test_defaults_and_conversion(self):
        # defaults
        headers = self.storage_class([
            ('Content-Type', 'text/plain'),
            ('X-Foo',        'bar'),
            ('X-Bar',        '1'),
            ('X-Bar',        '2')
        ])
        assert headers.getlist('x-bar') == ['1', '2']
        assert headers.get('x-Bar') == '1'
        assert headers.get('Content-Type') == 'text/plain'

        assert headers.setdefault('X-Foo', 'nope') == 'bar'
        assert headers.setdefault('X-Bar', 'nope') == '1'
        assert headers.setdefault('X-Baz', 'quux') == 'quux'
        assert headers.setdefault('X-Baz', 'nope') == 'quux'
        headers.pop('X-Baz')

        # type conversion
        assert headers.get('x-bar', type=int) == 1
        assert headers.getlist('x-bar', type=int) == [1, 2]

        # list like operations
        assert headers[0] == ('Content-Type', 'text/plain')
        assert headers[:1] == self.storage_class([('Content-Type', 'text/plain')])
        del headers[:2]
        del headers[-1]
        assert headers == self.storage_class([('X-Bar', '1')])

    def test_copying(self):
        a = self.storage_class([('foo', 'bar')])
        b = a.copy()
        a.add('foo', 'baz')
        assert a.getlist('foo') == ['bar', 'baz']
        assert b.getlist('foo') == ['bar']

    def test_popping(self):
        headers = self.storage_class([('a', 1)])
        assert headers.pop('a') == 1
        assert headers.pop('b', 2) == 2

        with pytest.raises(KeyError):
            headers.pop('c')

    def test_set_arguments(self):
        a = self.storage_class()
        a.set('Content-Disposition', 'useless')
        a.set('Content-Disposition', 'attachment', filename='foo')
        assert a['Content-Disposition'] == 'attachment; filename=foo'

    def test_reject_newlines(self):
        h = self.storage_class()

        for variation in 'foo\nbar', 'foo\r\nbar', 'foo\rbar':
            with pytest.raises(ValueError):
                h['foo'] = variation
            with pytest.raises(ValueError):
                h.add('foo', variation)
            with pytest.raises(ValueError):
                h.add('foo', 'test', option=variation)
            with pytest.raises(ValueError):
                h.set('foo', variation)
            with pytest.raises(ValueError):
                h.set('foo', 'test', option=variation)

    def test_slicing(self):
        # there's nothing wrong with these being native strings
        # Headers doesn't care about the data types
        h = self.storage_class()
        h.set('X-Foo-Poo', 'bleh')
        h.set('Content-Type', 'application/whocares')
        h.set('X-Forwarded-For', '192.168.0.123')
        h[:] = [(k, v) for k, v in h if k.startswith(u'X-')]
        assert list(h) == [
            ('X-Foo-Poo', 'bleh'),
            ('X-Forwarded-For', '192.168.0.123')
        ]

    def test_bytes_operations(self):
        h = self.storage_class()
        h.set('X-Foo-Poo', 'bleh')
        h.set('X-Whoops', b'\xff')

        assert h.get('x-foo-poo', as_bytes=True) == b'bleh'
        assert h.get('x-whoops', as_bytes=True) == b'\xff'

    def test_to_wsgi_list(self):
        h = self.storage_class()
        h.set(u'Key', u'Value')
        for key, value in h.to_wsgi_list():
            if PY2:
                strict_eq(key, b'Key')
                strict_eq(value, b'Value')
            else:
                strict_eq(key, u'Key')
                strict_eq(value, u'Value')


class TestEnvironHeaders(object):
    storage_class = datastructures.EnvironHeaders

    def test_basic_interface(self):
        # this happens in multiple WSGI servers because they
        # use a vary naive way to convert the headers;
        broken_env = {
            'HTTP_CONTENT_TYPE':        'text/html',
            'CONTENT_TYPE':             'text/html',
            'HTTP_CONTENT_LENGTH':      '0',
            'CONTENT_LENGTH':           '0',
            'HTTP_ACCEPT':              '*',
            'wsgi.version':             (1, 0)
        }
        headers = self.storage_class(broken_env)
        assert headers
        assert len(headers) == 3
        assert sorted(headers) == [
            ('Accept', '*'),
            ('Content-Length', '0'),
            ('Content-Type', 'text/html')
        ]
        assert not self.storage_class({'wsgi.version': (1, 0)})
        assert len(self.storage_class({'wsgi.version': (1, 0)})) == 0

    def test_return_type_is_unicode(self):
        # environ contains native strings; we return unicode
        headers = self.storage_class({
            'HTTP_FOO': '\xe2\x9c\x93',
            'CONTENT_TYPE': 'text/plain',
        })
        assert headers['Foo'] == u"\xe2\x9c\x93"
        assert isinstance(headers['Foo'], text_type)
        assert isinstance(headers['Content-Type'], text_type)
        iter_output = dict(iter(headers))
        assert iter_output['Foo'] == u"\xe2\x9c\x93"
        assert isinstance(iter_output['Foo'], text_type)
        assert isinstance(iter_output['Content-Type'], text_type)

    def test_bytes_operations(self):
        foo_val = '\xff'
        h = self.storage_class({
            'HTTP_X_FOO': foo_val
        })

        assert h.get('x-foo', as_bytes=True) == b'\xff'
        assert h.get('x-foo') == u'\xff'


class TestHeaderSet(object):
    storage_class = datastructures.HeaderSet

    def test_basic_interface(self):
        hs = self.storage_class()
        hs.add('foo')
        hs.add('bar')
        assert 'Bar' in hs
        assert hs.find('foo') == 0
        assert hs.find('BAR') == 1
        assert hs.find('baz') < 0
        hs.discard('missing')
        hs.discard('foo')
        assert hs.find('foo') < 0
        assert hs.find('bar') == 0

        with pytest.raises(IndexError):
            hs.index('missing')

        assert hs.index('bar') == 0
        assert hs
        hs.clear()
        assert not hs


class TestImmutableList(object):
    storage_class = datastructures.ImmutableList

    def test_list_hashable(self):
        t = (1, 2, 3, 4)
        l = self.storage_class(t)
        assert hash(t) == hash(l)
        assert t != l


def make_call_asserter(func=None):
    """Utility to assert a certain number of function calls.

    :param func: Additional callback for each function call.

    >>> assert_calls, func = make_call_asserter()
    >>> with assert_calls(2):
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


class TestCallbackDict(object):
    storage_class = datastructures.CallbackDict

    def test_callback_dict_reads(self):
        assert_calls, func = make_call_asserter()
        initial = {'a': 'foo', 'b': 'bar'}
        dct = self.storage_class(initial=initial, on_update=func)
        with assert_calls(0, 'callback triggered by read-only method'):
            # read-only methods
            dct['a']
            dct.get('a')
            pytest.raises(KeyError, lambda: dct['x'])
            'a' in dct
            list(iter(dct))
            dct.copy()
        with assert_calls(0, 'callback triggered without modification'):
            # methods that may write but don't
            dct.pop('z', None)
            dct.setdefault('a')

    def test_callback_dict_writes(self):
        assert_calls, func = make_call_asserter()
        initial = {'a': 'foo', 'b': 'bar'}
        dct = self.storage_class(initial=initial, on_update=func)
        with assert_calls(8, 'callback not triggered by write method'):
            # always-write methods
            dct['z'] = 123
            dct['z'] = 123  # must trigger again
            del dct['z']
            dct.pop('b', None)
            dct.setdefault('x')
            dct.popitem()
            dct.update([])
            dct.clear()
        with assert_calls(0, 'callback triggered by failed del'):
            pytest.raises(KeyError, lambda: dct.__delitem__('x'))
        with assert_calls(0, 'callback triggered by failed pop'):
            pytest.raises(KeyError, lambda: dct.pop('x'))


class TestCacheControl(object):

    def test_repr(self):
        cc = datastructures.RequestCacheControl(
            [("max-age", "0"), ("private", "True")],
        )
        assert repr(cc) == "<RequestCacheControl max-age='0' private='True'>"


class TestAccept(object):
    storage_class = datastructures.Accept

    def test_accept_basic(self):
        accept = self.storage_class([('tinker', 0), ('tailor', 0.333),
                                     ('soldier', 0.667), ('sailor', 1)])
        # check __getitem__ on indices
        assert accept[3] == ('tinker', 0)
        assert accept[2] == ('tailor', 0.333)
        assert accept[1] == ('soldier', 0.667)
        assert accept[0], ('sailor', 1)
        # check __getitem__ on string
        assert accept['tinker'] == 0
        assert accept['tailor'] == 0.333
        assert accept['soldier'] == 0.667
        assert accept['sailor'] == 1
        assert accept['spy'] == 0
        # check quality method
        assert accept.quality('tinker') == 0
        assert accept.quality('tailor') == 0.333
        assert accept.quality('soldier') == 0.667
        assert accept.quality('sailor') == 1
        assert accept.quality('spy') == 0
        # check __contains__
        assert 'sailor' in accept
        assert 'spy' not in accept
        # check index method
        assert accept.index('tinker') == 3
        assert accept.index('tailor') == 2
        assert accept.index('soldier') == 1
        assert accept.index('sailor') == 0
        with pytest.raises(ValueError):
            accept.index('spy')
        # check find method
        assert accept.find('tinker') == 3
        assert accept.find('tailor') == 2
        assert accept.find('soldier') == 1
        assert accept.find('sailor') == 0
        assert accept.find('spy') == -1
        # check to_header method
        assert accept.to_header() == \
            'sailor,soldier;q=0.667,tailor;q=0.333,tinker;q=0'
        # check best_match method
        assert accept.best_match(['tinker', 'tailor', 'soldier', 'sailor'],
                                 default=None) == 'sailor'
        assert accept.best_match(['tinker', 'tailor', 'soldier'],
                                 default=None) == 'soldier'
        assert accept.best_match(['tinker', 'tailor'], default=None) == \
            'tailor'
        assert accept.best_match(['tinker'], default=None) is None
        assert accept.best_match(['tinker'], default='x') == 'x'

    def test_accept_wildcard(self):
        accept = self.storage_class([('*', 0), ('asterisk', 1)])
        assert '*' in accept
        assert accept.best_match(['asterisk', 'star'], default=None) == \
            'asterisk'
        assert accept.best_match(['star'], default=None) is None

    @pytest.mark.skipif(True, reason='Werkzeug doesn\'t respect specificity.')
    def test_accept_wildcard_specificity(self):
        accept = self.storage_class([('asterisk', 0), ('star', 0.5), ('*', 1)])
        assert accept.best_match(['star', 'asterisk'], default=None) == 'star'
        assert accept.best_match(['asterisk', 'star'], default=None) == 'star'
        assert accept.best_match(['asterisk', 'times'], default=None) == \
            'times'
        assert accept.best_match(['asterisk'], default=None) is None


class TestFileStorage(object):
    storage_class = datastructures.FileStorage

    def test_mimetype_always_lowercase(self):
        file_storage = self.storage_class(content_type='APPLICATION/JSON')
        assert file_storage.mimetype == 'application/json'
