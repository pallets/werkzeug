# -*- coding: utf-8 -*-
"""
    werkzeug.urls test
    ~~~~~~~~~~~~~~~~~~

    Tests the URL features

    :copyright: (c) 2010 by the Project Name Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from nose import SkipTest
from nose.tools import assert_raises
from werkzeug import url_quote, url_unquote, url_quote_plus, \
     url_unquote_plus, url_encode, url_decode, url_fix, uri_to_iri, \
     iri_to_uri, Href, OrderedMultiDict


def test_quoting():
    """URL quoting"""
    assert url_quote(u'\xf6\xe4\xfc') == '%C3%B6%C3%A4%C3%BC'
    assert url_unquote(url_quote(u'#%="\xf6')) == u'#%="\xf6'
    assert url_quote_plus('foo bar') == 'foo+bar'
    assert url_unquote_plus('foo+bar') == 'foo bar'
    assert url_encode({'a': None, 'b': 'foo bar'}) == 'b=foo+bar'
    assert url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)') == \
           'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'


def test_url_decoding():
    """Test the URL decoding"""
    x = url_decode('foo=42&bar=23&uni=H%C3%A4nsel')
    assert x['foo'] == '42'
    assert x['bar'] == '23'
    assert x['uni'] == u'Hänsel'

    x = url_decode('foo=42;bar=23;uni=H%C3%A4nsel', separator=';')
    assert x['foo'] == '42'
    assert x['bar'] == '23'
    assert x['uni'] == u'Hänsel'

    x = url_decode('%C3%9Ch=H%C3%A4nsel', decode_keys=True)
    assert x[u'Üh'] == u'Hänsel'


def test_url_encoding():
    """Test the URL decoding"""
    assert url_encode({'foo': 'bar 45'}) == 'foo=bar+45'
    d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
    assert url_encode(d, sort=True) == 'bar=23&blah=H%C3%A4nsel&foo=1'
    assert url_encode(d, sort=True, separator=';') == 'bar=23;blah=H%C3%A4nsel;foo=1'


def test_sorted_url_encode():
    """Optional sorted URL encoding"""
    assert url_encode({"a": 42, "b": 23, 1: 1, 2: 2}, sort=True) == '1=1&2=2&a=42&b=23'
    assert url_encode({'A': 1, 'a': 2, 'B': 3, 'b': 4}, sort=True,
                      key=lambda x: x[0].lower()) == 'A=1&a=2&B=3&b=4'


def test_url_fixing():
    """URL fixing"""
    x = url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)')
    assert x == 'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

    x = url_fix('http://example.com/?foo=%2f%2f')
    assert x == 'http://example.com/?foo=%2f%2f'


def test_iri_support():
    """The IRI support"""
    assert_raises(UnicodeError, uri_to_iri, u'http://föö.com/')
    assert_raises(UnicodeError, iri_to_uri, 'http://föö.com/')
    assert uri_to_iri('http://xn--n3h.net/') == u'http://\u2603.net/'
    assert uri_to_iri('http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th') == \
        u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th'
    assert iri_to_uri(u'http://☃.net/') == 'http://xn--n3h.net/'
    assert iri_to_uri(u'http://üser:pässword@☃.net/påth') == \
        'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'

    assert uri_to_iri('http://test.com/%3Fmeh?foo=%26%2F') == \
        u'http://test.com/%3Fmeh?foo=%26%2F'

    # this should work as well, might break on 2.4 because of a broken
    # idna codec
    assert uri_to_iri('/foo') == u'/foo'
    assert iri_to_uri(u'/foo') == '/foo'


def test_ordered_multidict_encoding():
    """"Make sure URLs are properly encoded from OrderedMultiDicts"""
    d = OrderedMultiDict()
    d.add('foo', 1)
    d.add('foo', 2)
    d.add('foo', 3)
    d.add('bar', 0)
    d.add('foo', 4)
    assert url_encode(d) == 'foo=1&foo=2&foo=3&bar=0&foo=4'


def test_href():
    """Test the Href class"""
    x = Href('http://www.example.com/')
    assert x('foo') == 'http://www.example.com/foo'
    assert x.foo('bar') == 'http://www.example.com/foo/bar'
    assert x.foo('bar', x=42) == 'http://www.example.com/foo/bar?x=42'
    assert x.foo('bar', class_=42) == 'http://www.example.com/foo/bar?class=42'
    assert x.foo('bar', {'class': 42}) == 'http://www.example.com/foo/bar?class=42'
    assert_raises(AttributeError, lambda: x.__blah__)

    x = Href('blah')
    assert x.foo('bar') == 'blah/foo/bar'

    assert_raises(TypeError, x.foo, {"foo": 23}, x=42)

    x = Href('')
    assert x('foo') == 'foo'


def test_href_past_root():
    """Href() over root does not break the URL."""
    raise SkipTest('currently not implemented, stdlib bug?')
    base_href = Href('http://www.blagga.com/1/2/3')
    assert base_href('../foo') == 'http://www.blagga.com/1/2/foo'
    assert base_href('../../foo') == 'http://www.blagga.com/1/foo'
    assert base_href('../../../foo') == 'http://www.blagga.com/foo'
    assert base_href('../../../../foo') == 'http://www.blagga.com/foo'
    assert base_href('../../../../../foo') == 'http://www.blagga.com/foo'
    assert base_href('../../../../../../foo') == 'http://www.blagga.com/foo'
