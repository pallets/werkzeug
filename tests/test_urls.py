# -*- coding: utf-8 -*-
"""
    werkzeug.urls test
    ~~~~~~~~~~~~~~~~~~

    Tests the URL features

    :copyright: (c) 2009 by the Project Name Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import url_quote, url_unquote, url_quote_plus, \
     url_unquote_plus, url_encode, url_decode, url_fix, Href


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


def test_href():
    """Test the Href object"""
    href = Href('/foo')
    assert href('bar', 23) == '/foo/bar/23'
    # the class is mostly unit-tested from the class docstring
