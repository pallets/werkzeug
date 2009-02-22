# -*- coding: utf-8 -*-
"""
    werkzeug.http test
    ~~~~~~~~~~~~~~~~~~~

    :license: BSD license.
"""
from datetime import datetime

from nose.tools import assert_raises

from werkzeug.http import *
from werkzeug.utils import http_date
from werkzeug.datastructures import *


def test_accept():
    """Regular accept header parsing and behavior"""
    a = parse_accept_header('en-us,ru;q=0.5')
    assert a.values() == ['en-us', 'ru']
    assert a.best == 'en-us'
    assert a.find('ru') == 1
    assert_raises(IndexError, lambda: a.index('de'))
    assert a.to_header() == 'en-us,ru;q=0.5'


def test_mime_accept():
    """MIME accept header parsing and behavior"""
    a = parse_accept_header('text/xml,application/xml,application/xhtml+xml,'
                            'text/html;q=0.9,text/plain;q=0.8,'
                            'image/png,*/*;q=0.5', MIMEAccept)
    assert_raises(ValueError, lambda: a['missing'])
    assert a['image/png'] == 1
    assert a['text/plain'] == 0.8
    assert a['foo/bar'] == 0.5
    assert a[a.find('foo/bar')] == ('*/*', 0.5)


def test_charset_accept():
    """Charset accept header parsing and behavior"""
    a = parse_accept_header('ISO-8859-1,utf-8;q=0.7,*;q=0.7', CharsetAccept)
    assert a['iso-8859-1'] == a['iso8859-1'] == 1
    assert a['UTF8'] == 0.7
    assert a['ebcdic'] == 0.7


def test_language_accept():
    """Language accept header parsing and behavior"""
    a = parse_accept_header('de-AT,de;q=0.8,en;q=0.5', LanguageAccept)
    assert a.best == 'de-AT'
    assert 'de_AT' in a
    assert 'en' in a
    assert a['de-at'] == 1
    assert a['en'] == 0.5


def test_set_header():
    """Set header parsing and behavior"""
    hs = parse_set_header('foo, Bar, "Blah baz", Hehe')
    assert 'blah baz' in hs
    assert 'foobar' not in hs
    assert 'foo' in hs
    assert list(hs) == ['foo', 'Bar', 'Blah baz', 'Hehe']
    hs.add('Foo')
    assert hs.to_header() == 'foo, Bar, "Blah baz", Hehe'


def test_list_header():
    """List header parsing"""
    hl = parse_list_header('foo baz, blah')
    assert hl == ['foo baz', 'blah']


def test_dict_header():
    """Dict header parsing"""
    d = parse_dict_header('foo="bar baz", blah=42')
    assert d == {'foo': 'bar baz', 'blah': '42'}


def test_cache_control_header():
    """Cache control header parsing and behavior"""
    cc = parse_cache_control_header('max-age=0, no-cache')
    assert cc.max_age == 0
    assert cc.no_cache
    cc = parse_cache_control_header('private, community="UCI"', None,
                                    ResponseCacheControl)
    assert cc.private
    assert cc['community'] == 'UCI'

    c = ResponseCacheControl()
    assert c.no_cache is None
    assert c.private is None
    c.no_cache = True
    assert c.no_cache == '*'
    c.private = True
    assert c.private == '*'
    del c.private
    assert c.private is None
    assert c.to_header() == 'no-cache'


def test_authorization_header():
    """Authorization header parsing and behavior"""
    a = parse_authorization_header('Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==')
    assert a.type == 'basic'
    assert a.username == 'Aladdin'
    assert a.password == 'open sesame'

    a = parse_authorization_header('''Digest username="Mufasa",
                 realm="testrealm@host.invalid",
                 nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
                 uri="/dir/index.html",
                 qop=auth,
                 nc=00000001,
                 cnonce="0a4f113b",
                 response="6629fae49393a05397450978507c4ef1",
                 opaque="5ccc069c403ebaf9f0171e9517f40e41"''')
    assert a.type == 'digest'
    assert a.realm == 'testrealm@host.invalid'
    assert a.nonce == 'dcd98b7102dd2f0e8b11d0f600bfb0c093'
    assert a.uri == '/dir/index.html'
    assert 'auth' in a.qop
    assert a.nc == '00000001'
    assert a.cnonce == '0a4f113b'
    assert a.response == '6629fae49393a05397450978507c4ef1'
    assert a.opaque == '5ccc069c403ebaf9f0171e9517f40e41'


def test_www_authenticate_header():
    """WWW Authenticate header parsing and behavior"""
    wa = parse_www_authenticate_header('Basic realm="WallyWorld"')
    assert wa.type == 'basic'
    assert wa.realm == 'WallyWorld'
    wa.realm = 'Foo Bar'
    assert wa.to_header() == 'Basic realm="Foo Bar"'

    wa = parse_www_authenticate_header('''Digest
                 realm="testrealm@host.com",
                 qop="auth,auth-int",
                 nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
                 opaque="5ccc069c403ebaf9f0171e9517f40e41"''')
    assert wa.type == 'digest'
    assert wa.realm == 'testrealm@host.com'
    assert 'auth' in wa.qop
    assert 'auth-int' in wa.qop
    assert wa.nonce == 'dcd98b7102dd2f0e8b11d0f600bfb0c093'
    assert wa.opaque == '5ccc069c403ebaf9f0171e9517f40e41'


def test_etags():
    """ETag tools"""
    assert quote_etag('foo') == '"foo"'
    assert quote_etag('foo', True) == 'w/"foo"'
    assert unquote_etag('"foo"') == ('foo', False)
    assert unquote_etag('w/"foo"') == ('foo', True)
    es = parse_etags('"foo", "bar", w/"baz", blar')
    assert 'foo' in es
    assert 'baz' not in es
    assert es.contains_weak('baz')
    assert 'blar' in es
    assert es.contains_raw('w/"baz"')
    assert es.contains_raw('"foo"')
    assert sorted(es.to_header().split(', ')) == ['"bar"', '"blar"', '"foo"', 'w/"baz"']


def test_parse_date():
    """Date parsing"""
    assert parse_date('Sun, 06 Nov 1994 08:49:37 GMT    ') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date('Sunday, 06-Nov-94 08:49:37 GMT') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date(' Sun Nov  6 08:49:37 1994') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date('foo') is None


def test_remove_entity_headers():
    """Entity header removing function"""
    now = http_date()
    headers1 = [('Date', now), ('Content-Type', 'text/html'), ('Content-Length', '0')]
    headers2 = Headers(headers1)

    remove_entity_headers(headers1)
    assert headers1 == [('Date', now)]

    remove_entity_headers(headers2)
    assert headers2 == Headers([('Date', now)])


def test_remove_hop_by_hop_headers():
    """Hop-by-Hop header removing function"""
    headers1 = [('Connection', 'closed'), ('Foo', 'bar'),
                ('Keep-Alive', 'wtf')]
    headers2 = Headers(headers1)

    remove_hop_by_hop_headers(headers1)
    assert headers1 == [('Foo', 'bar')]

    remove_hop_by_hop_headers(headers2)
    assert headers2 == Headers([('Foo', 'bar')])
