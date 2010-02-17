# -*- coding: utf-8 -*-
from copy import copy
import pickle

from cStringIO import StringIO
from nose.tools import assert_raises
from werkzeug.datastructures import FileStorage, MultiDict, \
     ImmutableMultiDict, CombinedMultiDict, ImmutableTypeConversionDict, \
     ImmutableDict, Headers, ImmutableList, EnvironHeaders, \
     OrderedMultiDict, ImmutableOrderedMultiDict


def test_multidict_pickle():
    """MultiDict types are pickle-able"""
    for protocol in xrange(pickle.HIGHEST_PROTOCOL + 1):
        print 'pickling protocol', protocol
        d = MultiDict()
        d.setlist('foo', [1, 2, 3, 4])
        d.setlist('bar', 'foo bar baz'.split())
        s = pickle.dumps(d, protocol)
        ud = pickle.loads(s)
        assert type(ud) is type(d)
        assert ud == d
        assert pickle.loads(s.replace('werkzeug.datastructures', 'werkzeug')) == d
        ud['newkey'] = 'bla'
        assert ud != d

        d2 = OrderedMultiDict(d)
        d2.add('foo', 5)
        s = pickle.dumps(d2, protocol)
        ud = pickle.loads(s)
        assert type(ud) is type(d2)
        assert ud == d2
        ud['newkey'] = 'bla'
        print ud
        print d2
        assert ud != d2

        im = ImmutableMultiDict(d)
        assert im == d
        s = pickle.dumps(im, protocol)
        ud = pickle.loads(s)
        assert ud == im
        assert type(ud) is type(im)

        c = CombinedMultiDict([ud, im])
        cc = pickle.loads(pickle.dumps(c, protocol))
        assert c == cc
        assert type(c) is type(cc)


def test_immutable_dict_pickle():
    """ImmutableDicts are pickle-able"""
    for protocol in xrange(pickle.HIGHEST_PROTOCOL + 1):
        d = dict(foo="bar", blub="blah", meh=42)
        for dtype in ImmutableDict, ImmutableTypeConversionDict:
            nd = dtype(d)
            od = pickle.loads(pickle.dumps(nd, protocol))
            assert od == nd
            assert pickle.loads(pickle.dumps(nd, protocol) \
                .replace('werkzeug.datastructures', 'werkzeug')) == nd
            assert type(od) is type(nd)


def test_immutable_list_pickle():
    """ImmutableLists are pickle-able"""
    for protocol in xrange(pickle.HIGHEST_PROTOCOL + 1):
        l = ImmutableList(range(100))
        ul = pickle.loads(pickle.dumps(l, protocol))
        assert l == ul
        assert pickle.loads(pickle.dumps(l, protocol) \
            .replace('werkzeug.datastructures', 'werkzeug')) == l
        assert type(l) is type(ul)


def test_file_storage_truthiness():
    """Test FileStorage truthiness"""
    fs = FileStorage()
    assert not fs, 'should be False'

    fs = FileStorage(StringIO('Hello World'), filename='foo.txt')
    assert fs, 'should be True because of a provided filename'


def test_multidict():
    """Multidict behavior"""
    md = MultiDict()
    assert isinstance(md, dict)

    mapping = [('a', 1), ('b', 2), ('a', 2), ('d', 3),
               ('a', 1), ('a', 3), ('d', 4), ('c', 3)]
    md = MultiDict(mapping)

    # simple getitem gives the first value
    assert md['a'] == 1
    assert md['c'] == 3
    assert_raises(KeyError, lambda: md['e'])
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

    assert md.setlistdefault('u', [-1, -2]) == [-1, -2]
    assert md.getlist('u') == [-1, -2]
    assert md['u'] == -1

    # delitem
    del md['u']
    assert_raises(KeyError, lambda: md['u'])
    del md['d']
    assert md.getlist('d') == []

    # keys, values, items, lists
    assert list(sorted(md.keys())) == ['a', 'b', 'c']
    assert list(sorted(md.iterkeys())) == ['a', 'b', 'c']

    assert list(sorted(md.values())) == [1, 2, 3]
    assert list(sorted(md.itervalues())) == [1, 2, 3]

    assert list(sorted(md.items())) == [('a', 1), ('b', 2), ('c', 3)]
    assert list(sorted(md.items(multi=True))) == \
           [('a', 1), ('a', 2), ('a', 3), ('b', 2), ('c', 3)]
    assert list(sorted(md.iteritems())) == [('a', 1), ('b', 2), ('c', 3)]
    assert list(sorted(md.iteritems(multi=True))) == \
           [('a', 1), ('a', 2), ('a', 3), ('b', 2), ('c', 3)]

    assert list(sorted(md.lists())) == [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]
    assert list(sorted(md.iterlists())) == [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]

    # copy method
    copy = md.copy()
    assert copy['a'] == 1
    assert copy.getlist('a') == [1, 2, 3]

    # update with a multidict
    od = MultiDict([('a', 4), ('a', 5), ('y', 0)])
    md.update(od)
    assert md.getlist('a') == [1, 2, 3, 4, 5]
    assert md.getlist('y') == [0]

    # update with a regular dict
    md = copy
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
    md = MultiDict({'a': '4', 'b': ['2', '3']})
    assert md.get('a', type=int) == 4
    assert md.getlist('b', type=int) == [2, 3]

    # repr
    md = MultiDict([('a', 1), ('a', 2), ('b', 3)])
    assert "('a', 1)" in repr(md)
    assert "('a', 2)" in repr(md)
    assert "('b', 3)" in repr(md)

def test_combined_multidict():
    """Combined multidict behavior"""
    d1 = MultiDict([('foo', '1')])
    d2 = MultiDict([('bar', '2'), ('bar', '3')])
    d = CombinedMultiDict([d1, d2])

    # lookup
    assert d['foo'] == '1'
    assert d['bar'] == '2'
    assert d.getlist('bar') == ['2', '3']

    assert sorted(d.items()) == [('bar', '2'), ('foo', '1')], d.items()
    assert sorted(d.items(multi=True)) == [('bar', '2'), ('bar', '3'), ('foo', '1')]


    # type lookup
    assert d.get('foo', type=int) == 1
    assert d.getlist('bar', type=int) == [2, 3]

    # get key errors for missing stuff
    assert_raises(KeyError, lambda: d["missing"])

    # make sure that they are immutable
    def test_assign():
        d['foo'] = 'blub'
    assert_raises(TypeError, test_assign)

    # copies are immutable
    d = d.copy()
    assert_raises(TypeError, test_assign)

    # make sure lists merges
    md1 = MultiDict((("foo", "bar"),))
    md2 = MultiDict((("foo", "blafasel"),))
    x = CombinedMultiDict((md1, md2))
    assert x.lists() == [('foo', ['bar', 'blafasel'])]


def test_immutable_dict_copies_are_mutable():
    for cls in ImmutableTypeConversionDict, ImmutableMultiDict, ImmutableDict:
        immutable = cls({'a': 1})
        assert_raises(TypeError, immutable.pop, 'a')

        mutable = immutable.copy()
        mutable.pop('a')
        assert 'a' in immutable
        assert mutable is not immutable

        assert copy(immutable) is immutable


def test_headers():
    # simple header tests
    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('X-Foo', 'bar')
    assert 'x-Foo' in headers
    assert 'Content-type' in headers

    headers['Content-Type'] = 'foo/bar'
    assert headers['Content-Type'] == 'foo/bar'
    assert len(headers.getlist('Content-Type')) == 1

    # list conversion
    assert headers.to_list() == [
        ('Content-Type', 'foo/bar'),
        ('X-Foo', 'bar')
    ]
    assert str(headers) == (
        "Content-Type: foo/bar\r\n"
        "X-Foo: bar\r\n"
        "\r\n")
    assert str(Headers()) == "\r\n"

    # extended add
    headers.add('Content-Disposition', 'attachment', filename='foo')
    assert headers['Content-Disposition'] == 'attachment; filename=foo'

    headers.add('x', 'y', z='"')
    assert headers['x'] == r'y; z="\""'

    # defaults
    headers = Headers({
        'Content-Type': 'text/plain',
        'X-Foo':        'bar',
        'X-Bar':        ['1', '2']
    })
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
    assert headers[:1] == Headers([('Content-Type', 'text/plain')])
    del headers[:2]
    del headers[-1]
    assert headers == Headers([('X-Bar', '2')])

    # copying
    a = Headers([('foo', 'bar')])
    b = a.copy()
    a.add('foo', 'baz')
    assert a.getlist('foo') == ['bar', 'baz']
    assert b.getlist('foo') == ['bar']

    headers = Headers([('a', 1)])
    assert headers.pop('a') == 1
    assert headers.pop('b', 2) == 2
    assert_raises(KeyError, headers.pop, 'c')


def test_environ_headers_counts():
    """Ensure that the EnvironHeaders count correctly."""
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
    headers = EnvironHeaders(broken_env)
    assert headers
    assert len(headers) == 3
    assert sorted(headers) == [
        ('Accept', '*'),
        ('Content-Length', '0'),
        ('Content-Type', 'text/html')
    ]
    assert not EnvironHeaders({'wsgi.version': (1, 0)})
    assert len(EnvironHeaders({'wsgi.version': (1, 0)})) == 0


def test_multidict_pop():
    """Ensure pop from multidict works like it should"""
    make_d = lambda: MultiDict({'foo': [1, 2, 3, 4]})
    d = make_d()
    assert d.pop('foo') == 1
    assert not d
    d = make_d()
    assert d.pop('foo', 32) == 1
    assert not d
    d = make_d()
    assert d.pop('foos', 32) == 32
    assert d
    assert_raises(KeyError, d.pop, 'foos')


def test_ordered_multidict():
    """Test the OrderedMultiDict"""
    d = OrderedMultiDict()
    assert not d
    d.add('foo', 'bar')
    assert len(d) == 1
    d.add('foo', 'baz')
    assert len(d) == 1
    assert d.items() == [('foo', 'bar')]
    assert list(d) == ['foo']
    assert d.items(multi=True) == [('foo', 'bar'),
                                   ('foo', 'baz')]
    del d['foo']
    assert not d
    assert len(d) == 0
    assert list(d) == []

    d.update([('foo', 1), ('foo', 2), ('bar', 42)])
    d.add('foo', 3)
    assert d.getlist('foo') == [1, 2, 3]
    assert d.getlist('bar') == [42]
    assert d.items() == [('foo', 1), ('bar', 42)]
    assert d.keys() == list(d) == list(d.iterkeys()) == ['foo', 'bar']
    assert d.items(multi=True) == [('foo', 1), ('foo', 2),
                                   ('bar', 42), ('foo', 3)]
    assert len(d) == 2

    assert d.pop('foo') == 1
    assert d.pop('blafasel', None) is None
    assert d.pop('blafasel', 42) == 42
    assert len(d) == 1
    assert d.poplist('bar') == [42]
    assert not d

    d.add('foo', 42)
    d.add('foo', 23)
    d.add('bar', 2)
    d.add('foo', 42)
    assert d == MultiDict(d)
    id = ImmutableOrderedMultiDict(d)
    assert d == id
    d.add('foo', 2)
    assert d != id
