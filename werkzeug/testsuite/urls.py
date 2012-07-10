# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.urls
    ~~~~~~~~~~~~~~~~~~~~~~~

    URL helper tests.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

import unittest
from StringIO import StringIO

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug.datastructures import OrderedMultiDict
from werkzeug import urls


class URLsTestCase(WerkzeugTestCase):

    def test_quoting(self):
        assert urls.url_quote(u'\xf6\xe4\xfc') == '%C3%B6%C3%A4%C3%BC'
        assert urls.url_unquote(urls.url_quote(u'#%="\xf6')) == u'#%="\xf6'
        assert urls.url_quote_plus('foo bar') == 'foo+bar'
        assert urls.url_unquote_plus('foo+bar') == 'foo bar'
        assert urls.url_encode({'a': None, 'b': 'foo bar'}) == 'b=foo+bar'
        assert urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)') == \
               'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

    def test_url_decoding(self):
        x = urls.url_decode('foo=42&bar=23&uni=H%C3%A4nsel')
        assert x['foo'] == '42'
        assert x['bar'] == '23'
        assert x['uni'] == u'Hänsel'

        x = urls.url_decode('foo=42;bar=23;uni=H%C3%A4nsel', separator=';')
        assert x['foo'] == '42'
        assert x['bar'] == '23'
        assert x['uni'] == u'Hänsel'

        x = urls.url_decode('%C3%9Ch=H%C3%A4nsel', decode_keys=True)
        assert x[u'Üh'] == u'Hänsel'

    def test_streamed_url_decoding(self):
        item1 = 'a' * 100000
        item2 = 'b' * 400
        string = 'a=%s&b=%s&c=%s' % (item1, item2, item2)
        gen = urls.url_decode_stream(StringIO(string), limit=len(string),
                                     return_iterator=True)
        self.assert_equal(gen.next(), ('a', item1))
        self.assert_equal(gen.next(), ('b', item2))
        self.assert_equal(gen.next(), ('c', item2))
        self.assert_raises(StopIteration, gen.next)

    def test_url_encoding(self):
        assert urls.url_encode({'foo': 'bar 45'}) == 'foo=bar+45'
        d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
        assert urls.url_encode(d, sort=True) == 'bar=23&blah=H%C3%A4nsel&foo=1'
        assert urls.url_encode(d, sort=True, separator=';') == 'bar=23;blah=H%C3%A4nsel;foo=1'

    def test_sorted_url_encode(self):
        assert urls.url_encode({"a": 42, "b": 23, 1: 1, 2: 2}, sort=True) == '1=1&2=2&a=42&b=23'
        assert urls.url_encode({'A': 1, 'a': 2, 'B': 3, 'b': 4}, sort=True,
                          key=lambda x: x[0].lower()) == 'A=1&a=2&B=3&b=4'

    def test_streamed_url_encoding(self):
        out = StringIO()
        urls.url_encode_stream({'foo': 'bar 45'}, out)
        self.assert_equal(out.getvalue(), 'foo=bar+45')

        d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
        out = StringIO()
        urls.url_encode_stream(d, out, sort=True)
        self.assert_equal(out.getvalue(), 'bar=23&blah=H%C3%A4nsel&foo=1')
        out = StringIO()
        urls.url_encode_stream(d, out, sort=True, separator=';')
        self.assert_equal(out.getvalue(), 'bar=23;blah=H%C3%A4nsel;foo=1')

        gen = urls.url_encode_stream(d, sort=True)
        self.assert_equal(gen.next(), 'bar=23')
        self.assert_equal(gen.next(), 'blah=H%C3%A4nsel')
        self.assert_equal(gen.next(), 'foo=1')
        self.assert_raises(StopIteration, gen.next)

    def test_url_fixing(self):
        x = urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)')
        assert x == 'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

        x = urls.url_fix('http://example.com/?foo=%2f%2f')
        assert x == 'http://example.com/?foo=%2f%2f'

    def test_iri_support(self):
        urls.uri_to_iri(u'http://föö.com/')
        urls.iri_to_uri(u'http://föö.com/')
        assert urls.uri_to_iri('http://xn--n3h.net/') == u'http://\u2603.net/'
        assert urls.uri_to_iri('http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th') == \
            u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th'
        assert urls.iri_to_uri(u'http://☃.net/') == 'http://xn--n3h.net/'
        assert urls.iri_to_uri(u'http://üser:pässword@☃.net/påth') == \
            'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'

        assert urls.uri_to_iri('http://test.com/%3Fmeh?foo=%26%2F') == \
            u'http://test.com/%3Fmeh?foo=%26%2F'

        # this should work as well, might break on 2.4 because of a broken
        # idna codec
        assert urls.uri_to_iri('/foo') == u'/foo'
        assert urls.iri_to_uri(u'/foo') == '/foo'

    def test_ordered_multidict_encoding(self):
        d = OrderedMultiDict()
        d.add('foo', 1)
        d.add('foo', 2)
        d.add('foo', 3)
        d.add('bar', 0)
        d.add('foo', 4)
        assert urls.url_encode(d) == 'foo=1&foo=2&foo=3&bar=0&foo=4'

    def test_href(self):
        x = urls.Href('http://www.example.com/')
        assert x('foo') == 'http://www.example.com/foo'
        assert x.foo('bar') == 'http://www.example.com/foo/bar'
        assert x.foo('bar', x=42) == 'http://www.example.com/foo/bar?x=42'
        assert x.foo('bar', class_=42) == 'http://www.example.com/foo/bar?class=42'
        assert x.foo('bar', {'class': 42}) == 'http://www.example.com/foo/bar?class=42'
        self.assert_raises(AttributeError, lambda: x.__blah__)

        x = urls.Href('blah')
        assert x.foo('bar') == 'blah/foo/bar'

        self.assert_raises(TypeError, x.foo, {"foo": 23}, x=42)

        x = urls.Href('')
        assert x('foo') == 'foo'

    def test_href_url_join(self):
        x = urls.Href('test')
        assert x('foo:bar') == 'test/foo:bar'
        assert x('http://example.com/') == 'test/http://example.com/'

    if 0:
        # stdlib bug? :(
        def test_href_past_root(self):
            base_href = urls.Href('http://www.blagga.com/1/2/3')
            assert base_href('../foo') == 'http://www.blagga.com/1/2/foo'
            assert base_href('../../foo') == 'http://www.blagga.com/1/foo'
            assert base_href('../../../foo') == 'http://www.blagga.com/foo'
            assert base_href('../../../../foo') == 'http://www.blagga.com/foo'
            assert base_href('../../../../../foo') == 'http://www.blagga.com/foo'
            assert base_href('../../../../../../foo') == 'http://www.blagga.com/foo'

    def test_url_unquote_plus_unicode(self):
        # was broken in 0.6
        assert urls.url_unquote_plus(u'\x6d') == u'\x6d'
        assert type(urls.url_unquote_plus(u'\x6d')) is unicode

    def test_quoting_of_local_urls(self):
        rv = urls.iri_to_uri(u'/foo\x8f')
        assert rv == '/foo%C2%8F'
        assert type(rv) is str

    def test_iri_to_uri_idempotence_ascii_only(self):
        uri = u'http://www.idempoten.ce'
        uri = urls.iri_to_uri(uri)
        assert urls.iri_to_uri(uri) == uri

    def test_iri_to_uri_idempotence_non_ascii(self):
        uri = u'http://\N{SNOWMAN}/\N{SNOWMAN}'
        uri = urls.iri_to_uri(uri)
        assert urls.iri_to_uri(uri) == uri

    def test_uri_to_iri_idempotence_ascii_only(self):
        uri = 'http://www.idempoten.ce'
        uri = urls.uri_to_iri(uri)
        assert urls.uri_to_iri(uri) == uri

    def test_uri_to_iri_idempotence_non_ascii(self):
        uri = 'http://xn--n3h/%E2%98%83'
        uri = urls.uri_to_iri(uri)
        assert urls.uri_to_iri(uri) == uri

    def test_iri_to_uri_to_iri(self):
        iri = u'http://föö.com/'
        uri = urls.iri_to_uri(iri)
        assert urls.uri_to_iri(uri) == iri

    def test_uri_to_iri_to_uri(self):
        uri = 'http://xn--f-rgao.com/%C3%9E'
        iri = urls.uri_to_iri(uri)
        assert urls.iri_to_uri(iri) == uri

    def test_uri_iri_normalization(self):
        expected_uri = 'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93'
        expected_iri = u'http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713'

        tests = [
            u'http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713',
            u'http://xn--f-rgao.com/\u2610/fred?utf8=\N{CHECK MARK}',
            'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93',
            u'http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93',
            u'http://föñ.com/\u2610/fred?utf8=%E2%9C%93',
            'http://xn--f-rgao.com/\xe2\x98\x90/fred?utf8=\xe2\x9c\x93',
        ]

        for test in tests:
            assert urls.uri_to_iri(test) == expected_iri
            assert urls.iri_to_uri(test) == expected_uri
            assert urls.uri_to_iri(urls.iri_to_uri(test)) == expected_iri
            assert urls.iri_to_uri(urls.uri_to_iri(test)) == expected_uri
            assert urls.uri_to_iri(urls.uri_to_iri(test)) == expected_iri
            assert urls.iri_to_uri(urls.iri_to_uri(test)) == expected_uri


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(URLsTestCase))
    return suite
