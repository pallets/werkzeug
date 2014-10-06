# -*- coding: utf-8 -*-
"""
    tests.urls
    ~~~~~~~~~~

    URL helper tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

from tests import strict_eq

from werkzeug.datastructures import OrderedMultiDict
from werkzeug import urls
from werkzeug._compat import text_type, NativeStringIO, BytesIO


def test_parsing():
    url = urls.url_parse('http://anon:hunter2@[2001:db8:0:1]:80/a/b/c')
    assert url.netloc == 'anon:hunter2@[2001:db8:0:1]:80'
    assert url.username == 'anon'
    assert url.password == 'hunter2'
    assert url.port == 80
    assert url.ascii_host == '2001:db8:0:1'

    assert url.get_file_location() == (None, None)  # no file scheme


@pytest.mark.parametrize('implicit_format', (True, False))
@pytest.mark.parametrize('localhost', ('127.0.0.1', '::1', 'localhost'))
def test_fileurl_parsing_windows(implicit_format, localhost, monkeypatch):
    if implicit_format:
        pathformat = None
        monkeypatch.setattr('os.name', 'nt')
    else:
        pathformat = 'windows'
        monkeypatch.delattr('os.name')  # just to make sure it won't get used

    url = urls.url_parse('file:///C:/Documents and Settings/Foobar/stuff.txt')
    assert url.netloc == ''
    assert url.scheme == 'file'
    assert url.get_file_location(pathformat) == \
        (None, r'C:\Documents and Settings\Foobar\stuff.txt')

    url = urls.url_parse('file://///server.tld/file.txt')
    assert url.get_file_location(pathformat) == ('server.tld', r'file.txt')

    url = urls.url_parse('file://///server.tld')
    assert url.get_file_location(pathformat) == ('server.tld', '')

    url = urls.url_parse('file://///%s' % localhost)
    assert url.get_file_location(pathformat) == (None, '')

    url = urls.url_parse('file://///%s/file.txt' % localhost)
    assert url.get_file_location(pathformat) == (None, r'file.txt')


def test_replace():
    url = urls.url_parse('http://de.wikipedia.org/wiki/Troll')
    strict_eq(url.replace(query='foo=bar'),
                        urls.url_parse('http://de.wikipedia.org/wiki/Troll?foo=bar'))
    strict_eq(url.replace(scheme='https'),
                        urls.url_parse('https://de.wikipedia.org/wiki/Troll'))


def test_quoting():
    strict_eq(urls.url_quote(u'\xf6\xe4\xfc'), '%C3%B6%C3%A4%C3%BC')
    strict_eq(urls.url_unquote(urls.url_quote(u'#%="\xf6')), u'#%="\xf6')
    strict_eq(urls.url_quote_plus('foo bar'), 'foo+bar')
    strict_eq(urls.url_unquote_plus('foo+bar'), u'foo bar')
    strict_eq(urls.url_quote_plus('foo+bar'), 'foo%2Bbar')
    strict_eq(urls.url_unquote_plus('foo%2Bbar'), u'foo+bar')
    strict_eq(urls.url_encode({b'a': None, b'b': b'foo bar'}), 'b=foo+bar')
    strict_eq(urls.url_encode({u'a': None, u'b': u'foo bar'}), 'b=foo+bar')
    strict_eq(urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)'),
           'http://de.wikipedia.org/wiki/Elf%20(Begriffskl%C3%A4rung)')
    strict_eq(urls.url_quote_plus(42), '42')
    strict_eq(urls.url_quote(b'\xff'), '%FF')


def test_bytes_unquoting():
    strict_eq(urls.url_unquote(urls.url_quote(
        u'#%="\xf6', charset='latin1'), charset=None), b'#%="\xf6')


def test_url_decoding():
    x = urls.url_decode(b'foo=42&bar=23&uni=H%C3%A4nsel')
    strict_eq(x['foo'], u'42')
    strict_eq(x['bar'], u'23')
    strict_eq(x['uni'], u'Hänsel')

    x = urls.url_decode(b'foo=42;bar=23;uni=H%C3%A4nsel', separator=b';')
    strict_eq(x['foo'], u'42')
    strict_eq(x['bar'], u'23')
    strict_eq(x['uni'], u'Hänsel')

    x = urls.url_decode(b'%C3%9Ch=H%C3%A4nsel', decode_keys=True)
    strict_eq(x[u'Üh'], u'Hänsel')


def test_url_bytes_decoding():
    x = urls.url_decode(b'foo=42&bar=23&uni=H%C3%A4nsel', charset=None)
    strict_eq(x[b'foo'], b'42')
    strict_eq(x[b'bar'], b'23')
    strict_eq(x[b'uni'], u'Hänsel'.encode('utf-8'))


def test_streamed_url_decoding():
    item1 = u'a' * 100000
    item2 = u'b' * 400
    string = ('a=%s&b=%s&c=%s' % (item1, item2, item2)).encode('ascii')
    gen = urls.url_decode_stream(BytesIO(string), limit=len(string),
                                 return_iterator=True)
    strict_eq(next(gen), ('a', item1))
    strict_eq(next(gen), ('b', item2))
    strict_eq(next(gen), ('c', item2))
    pytest.raises(StopIteration, lambda: next(gen))


def test_stream_decoding_string_fails():
    pytest.raises(TypeError, urls.url_decode_stream, 'testing')


def test_url_encoding():
    strict_eq(urls.url_encode({'foo': 'bar 45'}), 'foo=bar+45')
    d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
    strict_eq(urls.url_encode(d, sort=True), 'bar=23&blah=H%C3%A4nsel&foo=1')
    strict_eq(urls.url_encode(d, sort=True, separator=u';'), 'bar=23;blah=H%C3%A4nsel;foo=1')


def test_sorted_url_encode():
    strict_eq(urls.url_encode({u"a": 42, u"b": 23, 1: 1, 2: 2},
        sort=True, key=lambda i: text_type(i[0])), '1=1&2=2&a=42&b=23')
    strict_eq(urls.url_encode({u'A': 1, u'a': 2, u'B': 3, 'b': 4}, sort=True,
                      key=lambda x: x[0].lower() + x[0]), 'A=1&a=2&B=3&b=4')


def test_streamed_url_encoding():
    out = NativeStringIO()
    urls.url_encode_stream({'foo': 'bar 45'}, out)
    strict_eq(out.getvalue(), 'foo=bar+45')

    d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
    out = NativeStringIO()
    urls.url_encode_stream(d, out, sort=True)
    strict_eq(out.getvalue(), 'bar=23&blah=H%C3%A4nsel&foo=1')
    out = NativeStringIO()
    urls.url_encode_stream(d, out, sort=True, separator=u';')
    strict_eq(out.getvalue(), 'bar=23;blah=H%C3%A4nsel;foo=1')

    gen = urls.url_encode_stream(d, sort=True)
    strict_eq(next(gen), 'bar=23')
    strict_eq(next(gen), 'blah=H%C3%A4nsel')
    strict_eq(next(gen), 'foo=1')
    pytest.raises(StopIteration, lambda: next(gen))


def test_url_fixing():
    x = urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)')
    assert x == 'http://de.wikipedia.org/wiki/Elf%20(Begriffskl%C3%A4rung)'

    x = urls.url_fix("http://just.a.test/$-_.+!*'(),")
    assert x == "http://just.a.test/$-_.+!*'(),"

    x = urls.url_fix('http://höhöhö.at/höhöhö/hähähä')
    assert x == r'http://xn--hhh-snabb.at/h%C3%B6h%C3%B6h%C3%B6/h%C3%A4h%C3%A4h%C3%A4'


def test_url_fixing_filepaths():
    x = urls.url_fix(r'file://C:\Users\Administrator\My Documents\ÑÈáÇíí')
    assert x == r'file:///C%3A/Users/Administrator/My%20Documents/%C3%91%C3%88%C3%A1%C3%87%C3%AD%C3%AD'

    a = urls.url_fix(r'file:/C:/')
    b = urls.url_fix(r'file://C:/')
    c = urls.url_fix(r'file:///C:/')
    assert a == b == c == r'file:///C%3A/'

    x = urls.url_fix(r'file://host/sub/path')
    assert x == r'file://host/sub/path'

    x = urls.url_fix(r'file:///')
    assert x == r'file:///'


def test_url_fixing_qs():
    x = urls.url_fix(b'http://example.com/?foo=%2f%2f')
    assert x == 'http://example.com/?foo=%2f%2f'

    x = urls.url_fix('http://acronyms.thefreedictionary.com/Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation')
    assert x == 'http://acronyms.thefreedictionary.com/Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation'


def test_iri_support():
    strict_eq(urls.uri_to_iri('http://xn--n3h.net/'),
                      u'http://\u2603.net/')
    strict_eq(
        urls.uri_to_iri(b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'),
                        u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th')
    strict_eq(urls.iri_to_uri(u'http://☃.net/'), 'http://xn--n3h.net/')
    strict_eq(
        urls.iri_to_uri(u'http://üser:pässword@☃.net/påth'),
                        'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th')

    strict_eq(urls.uri_to_iri('http://test.com/%3Fmeh?foo=%26%2F'),
                                      u'http://test.com/%3Fmeh?foo=%26%2F')

    # this should work as well, might break on 2.4 because of a broken
    # idna codec
    strict_eq(urls.uri_to_iri(b'/foo'), u'/foo')
    strict_eq(urls.iri_to_uri(u'/foo'), '/foo')

    strict_eq(urls.iri_to_uri(u'http://föö.com:8080/bam/baz'),
                      'http://xn--f-1gaa.com:8080/bam/baz')


def test_iri_safe_conversion():
    strict_eq(urls.iri_to_uri(u'magnet:?foo=bar'),
                             'magnet:?foo=bar')
    strict_eq(urls.iri_to_uri(u'itms-service://?foo=bar'),
                             'itms-service:?foo=bar')
    strict_eq(urls.iri_to_uri(u'itms-service://?foo=bar',
                                             safe_conversion=True),
                             'itms-service://?foo=bar')


def test_iri_safe_quoting():
    uri = 'http://xn--f-1gaa.com/%2F%25?q=%C3%B6&x=%3D%25#%25'
    iri = u'http://föö.com/%2F%25?q=ö&x=%3D%25#%25'
    strict_eq(urls.uri_to_iri(uri), iri)
    strict_eq(urls.iri_to_uri(urls.uri_to_iri(uri)), uri)


def test_ordered_multidict_encoding():
    d = OrderedMultiDict()
    d.add('foo', 1)
    d.add('foo', 2)
    d.add('foo', 3)
    d.add('bar', 0)
    d.add('foo', 4)
    assert urls.url_encode(d) == 'foo=1&foo=2&foo=3&bar=0&foo=4'


def test_multidict_encoding():
    d = OrderedMultiDict()
    d.add('2013-10-10T23:26:05.657975+0000', '2013-10-10T23:26:05.657975+0000')
    assert urls.url_encode(d) == '2013-10-10T23%3A26%3A05.657975%2B0000=2013-10-10T23%3A26%3A05.657975%2B0000'


def test_href():
    x = urls.Href('http://www.example.com/')
    strict_eq(x(u'foo'), 'http://www.example.com/foo')
    strict_eq(x.foo(u'bar'), 'http://www.example.com/foo/bar')
    strict_eq(x.foo(u'bar', x=42), 'http://www.example.com/foo/bar?x=42')
    strict_eq(x.foo(u'bar', class_=42), 'http://www.example.com/foo/bar?class=42')
    strict_eq(x.foo(u'bar', {u'class': 42}), 'http://www.example.com/foo/bar?class=42')
    pytest.raises(AttributeError, lambda: x.__blah__)

    x = urls.Href('blah')
    strict_eq(x.foo(u'bar'), 'blah/foo/bar')

    pytest.raises(TypeError, x.foo, {u"foo": 23}, x=42)

    x = urls.Href('')
    strict_eq(x('foo'), 'foo')


def test_href_url_join():
    x = urls.Href(u'test')
    assert x(u'foo:bar') == u'test/foo:bar'
    assert x(u'http://example.com/') == u'test/http://example.com/'
    assert x.a() == u'test/a'


def test_href_past_root():
    base_href = urls.Href('http://www.blagga.com/1/2/3')
    strict_eq(base_href('../foo'), 'http://www.blagga.com/1/2/foo')
    strict_eq(base_href('../../foo'), 'http://www.blagga.com/1/foo')
    strict_eq(base_href('../../../foo'), 'http://www.blagga.com/foo')
    strict_eq(base_href('../../../../foo'), 'http://www.blagga.com/foo')
    strict_eq(base_href('../../../../../foo'), 'http://www.blagga.com/foo')
    strict_eq(base_href('../../../../../../foo'), 'http://www.blagga.com/foo')


def test_url_unquote_plus_unicode():
    # was broken in 0.6
    strict_eq(urls.url_unquote_plus(u'\x6d'), u'\x6d')
    assert type(urls.url_unquote_plus(u'\x6d')) is text_type


def test_quoting_of_local_urls():
    rv = urls.iri_to_uri(u'/foo\x8f')
    strict_eq(rv, '/foo%C2%8F')
    assert type(rv) is str


def test_url_attributes():
    rv = urls.url_parse('http://foo%3a:bar%3a@[::1]:80/123?x=y#frag')
    strict_eq(rv.scheme, 'http')
    strict_eq(rv.auth, 'foo%3a:bar%3a')
    strict_eq(rv.username, u'foo:')
    strict_eq(rv.password, u'bar:')
    strict_eq(rv.raw_username, 'foo%3a')
    strict_eq(rv.raw_password, 'bar%3a')
    strict_eq(rv.host, '::1')
    assert rv.port == 80
    strict_eq(rv.path, '/123')
    strict_eq(rv.query, 'x=y')
    strict_eq(rv.fragment, 'frag')

    rv = urls.url_parse(u'http://\N{SNOWMAN}.com/')
    strict_eq(rv.host, u'\N{SNOWMAN}.com')
    strict_eq(rv.ascii_host, 'xn--n3h.com')


def test_url_attributes_bytes():
    rv = urls.url_parse(b'http://foo%3a:bar%3a@[::1]:80/123?x=y#frag')
    strict_eq(rv.scheme, b'http')
    strict_eq(rv.auth, b'foo%3a:bar%3a')
    strict_eq(rv.username, u'foo:')
    strict_eq(rv.password, u'bar:')
    strict_eq(rv.raw_username, b'foo%3a')
    strict_eq(rv.raw_password, b'bar%3a')
    strict_eq(rv.host, b'::1')
    assert rv.port == 80
    strict_eq(rv.path, b'/123')
    strict_eq(rv.query, b'x=y')
    strict_eq(rv.fragment, b'frag')


def test_url_joining():
    strict_eq(urls.url_join('/foo', '/bar'), '/bar')
    strict_eq(urls.url_join('http://example.com/foo', '/bar'),
                             'http://example.com/bar')
    strict_eq(urls.url_join('file:///tmp/', 'test.html'),
                             'file:///tmp/test.html')
    strict_eq(urls.url_join('file:///tmp/x', 'test.html'),
                             'file:///tmp/test.html')
    strict_eq(urls.url_join('file:///tmp/x', '../../../x.html'),
                             'file:///x.html')


def test_partial_unencoded_decode():
    ref = u'foo=정상처리'.encode('euc-kr')
    x = urls.url_decode(ref, charset='euc-kr')
    strict_eq(x['foo'], u'정상처리')


def test_iri_to_uri_idempotence_ascii_only():
    uri = u'http://www.idempoten.ce'
    uri = urls.iri_to_uri(uri)
    assert urls.iri_to_uri(uri) == uri


def test_iri_to_uri_idempotence_non_ascii():
    uri = u'http://\N{SNOWMAN}/\N{SNOWMAN}'
    uri = urls.iri_to_uri(uri)
    assert urls.iri_to_uri(uri) == uri


def test_uri_to_iri_idempotence_ascii_only():
    uri = 'http://www.idempoten.ce'
    uri = urls.uri_to_iri(uri)
    assert urls.uri_to_iri(uri) == uri


def test_uri_to_iri_idempotence_non_ascii():
    uri = 'http://xn--n3h/%E2%98%83'
    uri = urls.uri_to_iri(uri)
    assert urls.uri_to_iri(uri) == uri


def test_iri_to_uri_to_iri():
    iri = u'http://föö.com/'
    uri = urls.iri_to_uri(iri)
    assert urls.uri_to_iri(uri) == iri


def test_uri_to_iri_to_uri():
    uri = 'http://xn--f-rgao.com/%C3%9E'
    iri = urls.uri_to_iri(uri)
    assert urls.iri_to_uri(iri) == uri


def test_uri_iri_normalization():
    uri = 'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93'
    iri = u'http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713'

    tests = [
        u'http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713',
        u'http://xn--f-rgao.com/\u2610/fred?utf8=\N{CHECK MARK}',
        b'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93',
        u'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93',
        u'http://föñ.com/\u2610/fred?utf8=%E2%9C%93',
        b'http://xn--f-rgao.com/\xe2\x98\x90/fred?utf8=\xe2\x9c\x93',
    ]

    for test in tests:
        assert urls.uri_to_iri(test) == iri
        assert urls.iri_to_uri(test) == uri
        assert urls.uri_to_iri(urls.iri_to_uri(test)) == iri
        assert urls.iri_to_uri(urls.uri_to_iri(test)) == uri
        assert urls.uri_to_iri(urls.uri_to_iri(test)) == iri
        assert urls.iri_to_uri(urls.iri_to_uri(test)) == uri
