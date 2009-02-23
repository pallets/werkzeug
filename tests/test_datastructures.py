# -*- coding: utf-8 -*-
from nose.tools import assert_raises
from werkzeug.datastructures import *


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
    assert list(sorted(md.iteritems())) == [('a', 1), ('b', 2), ('c', 3)]

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


def test_combined_multidict():
    """Combined multidict behavior"""
    d1 = MultiDict([('foo', '1')])
    d2 = MultiDict([('bar', '2'), ('bar', '3')])
    d = CombinedMultiDict([d1, d2])

    # lookup
    assert d['foo'] == '1'
    assert d['bar'] == '2'
    assert d.getlist('bar') == ['2', '3']

    # type lookup
    assert d.get('foo', type=int) == 1
    assert d.getlist('bar', type=int) == [2, 3]

    # get key errors for missing stuff
    assert_raises(KeyError, lambda: d["missing"])

    # make sure that they are immutable
    def test_assign():
        d['foo'] = 'blub'
    assert_raises(TypeError, test_assign)

    # make sure lists merges
    md1 = MultiDict((("foo", "bar"),))
    md2 = MultiDict((("foo", "blafasel"),))
    x = CombinedMultiDict((md1, md2))
    assert x.lists() == [('foo', ['bar', 'blafasel'])]


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
