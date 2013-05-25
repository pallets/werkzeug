# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.urls
    ~~~~~~~~~~~~~~~~~~~~~~~

    URL helper tests.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug.datastructures import OrderedMultiDict
from werkzeug import urls
from werkzeug._compat import PY2, text_type, BytesIO


class URLsTestCase(WerkzeugTestCase):

    def test_quoting(self):
        self.assert_strict_equal(urls.url_quote(u'\xf6\xe4\xfc'), b'%C3%B6%C3%A4%C3%BC')
        self.assert_strict_equal(urls.url_unquote(urls.url_quote(u'#%="\xf6')), u'#%="\xf6')
        self.assert_strict_equal(urls.url_quote_plus('foo bar'), b'foo+bar')
        self.assert_strict_equal(urls.url_unquote_plus('foo+bar'), u'foo bar')
        self.assert_strict_equal(urls.url_encode({b'a': None, b'b': b'foo bar'}), b'b=foo+bar')
        self.assert_strict_equal(urls.url_encode({u'a': None, u'b': u'foo bar'}), b'b=foo+bar')
        self.assert_strict_equal(urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)'),
               u'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29')

    def test_url_decoding(self):
        x = urls.url_decode(b'foo=42&bar=23&uni=H%C3%A4nsel')
        self.assert_strict_equal(x['foo'], u'42')
        self.assert_strict_equal(x['bar'], u'23')
        self.assert_strict_equal(x['uni'], u'Hänsel')

        x = urls.url_decode(b'foo=42;bar=23;uni=H%C3%A4nsel', separator=b';')
        self.assert_strict_equal(x['foo'], u'42')
        self.assert_strict_equal(x['bar'], u'23')
        self.assert_strict_equal(x['uni'], u'Hänsel')

        x = urls.url_decode(b'%C3%9Ch=H%C3%A4nsel', decode_keys=True)
        self.assert_strict_equal(x[u'Üh'], u'Hänsel')

    def test_streamed_url_decoding(self):
        item1 = u'a' * 100000
        item2 = u'b' * 400
        string = ('a=%s&b=%s&c=%s' % (item1, item2, item2)).encode('ascii')
        gen = urls.url_decode_stream(BytesIO(string), limit=len(string),
                                     return_iterator=True)
        self.assert_strict_equal(next(gen), ('a', item1))
        self.assert_strict_equal(next(gen), ('b', item2))
        self.assert_strict_equal(next(gen), ('c', item2))
        self.assert_raises(StopIteration, lambda: next(gen))

    def test_url_encoding(self):
        self.assert_strict_equal(urls.url_encode({'foo': 'bar 45'}), b'foo=bar+45')
        d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
        self.assert_strict_equal(urls.url_encode(d, sort=True), b'bar=23&blah=H%C3%A4nsel&foo=1')
        self.assert_strict_equal(urls.url_encode(d, sort=True, separator=u';'), b'bar=23;blah=H%C3%A4nsel;foo=1')

    def test_sorted_url_encode(self):
        self.assert_strict_equal(urls.url_encode({u"a": 42, u"b": 23, 1: 1, 2: 2}, sort=True, key=lambda i: text_type(i[0])), b'1=1&2=2&a=42&b=23')
        self.assert_strict_equal(urls.url_encode({u'A': 1, u'a': 2, u'B': 3, 'b': 4}, sort=True,
                          key=lambda x: x[0].lower() + x[0]), b'A=1&a=2&B=3&b=4')

    def test_streamed_url_encoding(self):
        out = BytesIO()
        urls.url_encode_stream({'foo': 'bar 45'}, out)
        self.assert_strict_equal(out.getvalue(), b'foo=bar+45')

        d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
        out = BytesIO()
        urls.url_encode_stream(d, out, sort=True)
        self.assert_strict_equal(out.getvalue(), b'bar=23&blah=H%C3%A4nsel&foo=1')
        out = BytesIO()
        urls.url_encode_stream(d, out, sort=True, separator=u';')
        self.assert_strict_equal(out.getvalue(), b'bar=23;blah=H%C3%A4nsel;foo=1')

        gen = urls.url_encode_stream(d, sort=True)
        self.assert_strict_equal(next(gen), b'bar=23')
        self.assert_strict_equal(next(gen), b'blah=H%C3%A4nsel')
        self.assert_strict_equal(next(gen), b'foo=1')
        self.assert_raises(StopIteration, lambda: next(gen))

    def test_url_fixing(self):
        x = urls.url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)')
        self.assert_line_equal(x, 'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29')

    def test_url_fixing_qs(self):
        x = urls.url_fix(b'http://example.com/?foo=%2f%2f')
        self.assert_line_equal(x, b'http://example.com/?foo=%2f%2f')

        x = urls.url_fix('http://acronyms.thefreedictionary.com/Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation')
        self.assert_equal(x, b'http://acronyms.thefreedictionary.com/Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation')

    def test_iri_support(self):
        if PY2:
            self.assert_raises(UnicodeError, urls.uri_to_iri, u'http://föö.com/')
        self.assert_strict_equal(urls.uri_to_iri('http://xn--n3h.net/'),
                          u'http://\u2603.net/')
        self.assert_strict_equal(
            urls.uri_to_iri(b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'),
                            u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th')
        self.assert_strict_equal(urls.iri_to_uri(u'http://☃.net/'), b'http://xn--n3h.net/')
        self.assert_strict_equal(
            urls.iri_to_uri(u'http://üser:pässword@☃.net/påth'),
                            b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th')

        self.assert_strict_equal(urls.uri_to_iri('http://test.com/%3Fmeh?foo=%26%2F'),
                                          u'http://test.com/%3Fmeh?foo=%26%2F')

        # this should work as well, might break on 2.4 because of a broken
        # idna codec
        self.assert_strict_equal(urls.uri_to_iri(b'/foo'), u'/foo')
        self.assert_strict_equal(urls.iri_to_uri(u'/foo'), b'/foo')

        self.assert_strict_equal(urls.iri_to_uri(u'http://föö.com:8080/bam/baz'),
                          b'http://xn--f-1gaa.com:8080/bam/baz')

    def test_ordered_multidict_encoding(self):
        d = OrderedMultiDict()
        d.add('foo', 1)
        d.add('foo', 2)
        d.add('foo', 3)
        d.add('bar', 0)
        d.add('foo', 4)
        self.assert_equal(urls.url_encode(d), b'foo=1&foo=2&foo=3&bar=0&foo=4')

    def test_href(self):
        x = urls.Href(u'http://www.example.com/')
        self.assert_strict_equal(x(u'foo'), u'http://www.example.com/foo')
        self.assert_strict_equal(x.foo(u'bar'), u'http://www.example.com/foo/bar')
        self.assert_strict_equal(x.foo(u'bar', x=42), u'http://www.example.com/foo/bar?x=42')
        self.assert_strict_equal(x.foo(u'bar', class_=42), u'http://www.example.com/foo/bar?class=42')
        self.assert_strict_equal(x.foo(u'bar', {u'class': 42}), u'http://www.example.com/foo/bar?class=42')
        self.assert_raises(AttributeError, lambda: x.__blah__)

        x = urls.Href(u'blah')
        self.assert_strict_equal(x.foo(u'bar'), u'blah/foo/bar')

        self.assert_raises(TypeError, x.foo, {u"foo": 23}, x=42)

        x = urls.Href(u'')
        self.assert_strict_equal(x(u'foo'), u'foo')

    def test_href_url_join(self):
        x = urls.Href(u'test')
        self.assert_line_equal(x(u'foo:bar'), u'test/foo:bar')
        self.assert_line_equal(x(u'http://example.com/'), u'test/http://example.com/')
        self.assert_line_equal(x.a(), u'test/a')

    if 0:
        # stdlib bug? :(
        def test_href_past_root(self):
            base_href = urls.Href('http://www.blagga.com/1/2/3')
            self.assert_strict_equal(base_href('../foo'), 'http://www.blagga.com/1/2/foo')
            self.assert_strict_equal(base_href('../../foo'), 'http://www.blagga.com/1/foo')
            self.assert_strict_equal(base_href('../../../foo'), 'http://www.blagga.com/foo')
            self.assert_strict_equal(base_href('../../../../foo'), 'http://www.blagga.com/foo')
            self.assert_strict_equal(base_href('../../../../../foo'), 'http://www.blagga.com/foo')
            self.assert_strict_equal(base_href('../../../../../../foo'), 'http://www.blagga.com/foo')

    def test_url_unquote_plus_unicode(self):
        # was broken in 0.6
        self.assert_strict_equal(urls.url_unquote_plus(u'\x6d'), u'\x6d')
        self.assert_is(type(urls.url_unquote_plus(u'\x6d')), text_type)

    def test_quoting_of_local_urls(self):
        rv = urls.iri_to_uri(u'/foo\x8f')
        self.assert_strict_equal(rv, b'/foo%C2%8F')
        self.assert_is(type(rv), bytes)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(URLsTestCase))
    return suite
