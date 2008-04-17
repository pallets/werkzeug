# -*- coding: utf-8 -*-
"""
    werkzeug.http test
    ~~~~~~~~~~~~~~~~~~~

    :license: BSD license.
"""
from datetime import datetime
from py.test import raises
from werkzeug.http import *


def test_accept():
    a = parse_accept_header('en-us,ru;q=0.5')
    assert a.values() == ['en-us', 'ru']
    assert a.best == 'en-us'
    assert a.find('ru') == 1
    raises(IndexError, lambda: a.index('de'))

    a = parse_accept_header('text/xml,application/xml,application/xhtml+xml,'
                            'text/html;q=0.9,text/plain;q=0.8,'
                            'image/png,*/*;q=0.5')
    assert a['missing'] == 0
    assert a['image/png'] == 1
    assert a['text/plain'] == 0.8


def test_set_header():
    hs = parse_set_header('foo, Bar, "Blah baz", Hehe')
    assert 'blah baz' in hs
    assert 'foobar' not in hs
    assert 'foo' in hs
    assert list(hs) == ['foo', 'Bar', 'Blah baz', 'Hehe']
    hs.add('Foo')
    assert hs.to_header() == 'foo, Bar, Blah baz, Hehe'


def test_list_header():
    hl = parse_list_header('foo baz, blah')
    assert hl == ['foo baz', 'blah']


def test_dict_header():
    d = parse_dict_header('foo="bar baz", blah=42')
    assert d == {'foo': 'bar baz', 'blah': '42'}


def test_cache_control_header():
    cc = parse_cache_control_header('max-age=0, no-cache')
    assert cc.max_age == 0
    assert cc.no_cache
    cc = parse_cache_control_header('private, community="UCI"')
    assert cc.private
    assert cc['community'] == 'UCI'


def test_authorization_header():
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
    assert parse_date('Sun, 06 Nov 1994 08:49:37 GMT    ') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date('Sunday, 06-Nov-94 08:49:37 GMT') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date(' Sun Nov  6 08:49:37 1994') == datetime(1994, 11, 6, 8, 49, 37)
    assert parse_date('foo') is None
