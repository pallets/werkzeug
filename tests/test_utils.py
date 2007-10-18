# -*- coding: utf-8 -*-
"""
    werkzeug.utils test
    ~~~~~~~~~~~~~~~~~~~

    :copyright: 2007 by Georg Brandl.
    :license: BSD license.
"""

from py.test import raises

from werkzeug.utils import MultiDict, CombinedMultiDict, Headers, \
     lazy_property, environ_property, url_decode, url_encode, url_quote, \
     url_unquote, url_quote_plus, url_unquote_plus, escape


def test_multidict():
    md = MultiDict()
    assert isinstance(md, dict)

    mapping = [('a', 1), ('b', 2), ('a', 2), ('d', 3),
               ('a', 1), ('a', 3), ('d', 4), ('c', 3)]
    md = MultiDict(mapping)

    # simple getitem gives the first value
    assert md['a'] == 1
    assert md['c'] == 3
    raises(KeyError, "md['e']")
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
    raises(KeyError, "md['u']")
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

    # remaining: b=2, c=3
    popped = md.popitem()
    assert popped in [('b', 2), ('c', 3)]
    popped = md.popitemlist()
    assert popped in [('b', [2]), ('c', [3])]


def test_combined_multidict():
    d1 = MultiDict([('foo', 1)])
    d2 = MultiDict([('bar', 2)])
    d = CombinedMultiDict([d1, d2])

    # lookup
    assert d['foo'] == 1
    assert d['bar'] == 2

    # get key errors for missing stuff
    raises(KeyError, 'd["missing"]')

    # make sure that they are immutable
    raises(TypeError, 'd["foo"] = "blub"')


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
        ('X-Foo', 'bar'),
        ('Content-Type', 'foo/bar')
    ]

    # defaults
    headers = Headers({
        'Content-Type': 'text/plain',
        'X-Foo':        'bar',
        'X-Bar':        ['1', '2']
    })
    assert headers.getlist('x-bar') == ['1', '2']
    assert headers.get('x-Bar') == '1'
    assert headers.get('Content-Type') == 'text/plain'

    # copying
    a = Headers([('foo', 'bar')])
    b = a.copy()
    a.add('foo', 'baz')
    assert a.getlist('foo') == ['bar', 'baz']
    assert b.getlist('foo') == ['bar']


def test_lazy_property():
    foo = []
    class A(object):
        def prop(self):
            foo.append(42)
            return 42
        prop = lazy_property(prop)

    a = A()
    p = a.prop
    q = a.prop
    assert p == q == 42
    assert foo == [42]

    foo = []
    class A(object):
        def prop(self):
            foo.append(42)
            return 42
        prop = lazy_property(prop, name='propval')

    a = A()
    p = a.prop
    q = a.prop
    r = a.propval
    assert p == q == r == 42
    assert foo == [42, 42]


def test_environ_property():
    class A(object):
        environ = {'string': 'abc', 'number': '42'}

        string = environ_property('string')
        missing = environ_property('missing', 'spam')
        read_only = environ_property('number', read_only=True)
        number = environ_property('number', convert=int)
        broken_number = environ_property('broken_number', convert=int)

    a = A()
    assert a.string == 'abc'
    assert a.missing == 'spam'
    raises(AttributeError, 'a.read_only = "something"')
    assert a.number == 42
    assert a.broken_number == None


def test_quoting():
    assert url_quote(u'\xf6\xe4\xfc') == '%C3%B6%C3%A4%C3%BC'
    assert url_unquote(url_quote(u'#%="\xf6')) == u'#%="\xf6'
    assert url_quote_plus('foo bar') == 'foo+bar'
    assert url_unquote_plus('foo+bar') == 'foo bar'


def test_escape():
    assert escape('<>') == '&lt;&gt;'
    assert escape('"foo"') == '"foo"'
    assert escape('"foo"', True) == '&quot;foo&quot;'
