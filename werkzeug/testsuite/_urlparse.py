from werkzeug.testsuite import WerkzeugTestCase
import unittest
import werkzeug._urlparse as urlparse
import six

RFC1808_BASE = u"http://a/b/c/d;p?q#f"
RFC2396_BASE = u"http://a/b/c/d;p?q"
RFC3986_BASE = u'http://a/b/c/d;p?q'
SIMPLE_BASE  = u'http://a/b/c/d'

# A list of test cases.  Each test case is a two-tuple that contains
# a string with the query and a dictionary with the expected result.

parse_qsl_test_cases = [
    (u"", []),
    (u"&", []),
    (u"&&", []),
    (u"=", [(u'', u'')]),
    (u"=a", [(u'', u'a')]),
    (u"a", [(u'a', u'')]),
    (u"a=", [(u'a', u'')]),
    (u"a=", [(u'a', u'')]),
    (u"&a=b", [(u'a', u'b')]),
    (u"a=a+b&b=b+c", [(u'a', u'a b'), (u'b', u'b c')]),
    (u"a=1&a=2", [(u'a', u'1'), (u'a', u'2')]),
    (b"", []),
    (b"&", []),
    (b"&&", []),
    (b"=", [(b'', b'')]),
    (b"=a", [(b'', b'a')]),
    (b"a", [(b'a', b'')]),
    (b"a=", [(b'a', b'')]),
    (b"a=", [(b'a', b'')]),
    (b"&a=b", [(b'a', b'b')]),
    (b"a=a+b&b=b+c", [(b'a', b'a b'), (b'b', b'b c')]),
    (b"a=1&a=2", [(b'a', b'1'), (b'a', b'2')]),
]

class UrlParseTestCase(WerkzeugTestCase):

    def checkRoundtrips(self, url, parsed, split):
        result = urlparse.urlparse(url)
        self.assertEqual(result, parsed)
        t = (result.scheme, result.netloc, result.path,
             result.params, result.query, result.fragment)
        self.assertEqual(t, parsed)
        # put it back together and it should be the same
        result2 = urlparse.urlunparse(result)
        self.assertEqual(result2, url)
        self.assertEqual(result2, result.geturl())

        # the result of geturl() is a fixpoint; we can always parse it
        # again to get the same result:
        result3 = urlparse.urlparse(result.geturl())
        self.assertEqual(result3.geturl(), result.geturl())
        self.assertEqual(result3,          result)
        self.assertEqual(result3.scheme,   result.scheme)
        self.assertEqual(result3.netloc,   result.netloc)
        self.assertEqual(result3.path,     result.path)
        self.assertEqual(result3.params,   result.params)
        self.assertEqual(result3.query,    result.query)
        self.assertEqual(result3.fragment, result.fragment)
        self.assertEqual(result3.username, result.username)
        self.assertEqual(result3.password, result.password)
        self.assertEqual(result3.hostname, result.hostname)
        self.assertEqual(result3.port,     result.port)

        # check the roundtrip using urlsplit() as well
        result = urlparse.urlsplit(url)
        self.assertEqual(result, split)
        t = (result.scheme, result.netloc, result.path,
             result.query, result.fragment)
        self.assertEqual(t, split)
        result2 = urlparse.urlunsplit(result)
        self.assertEqual(result2, url)
        self.assertEqual(result2, result.geturl())

        # check the fixpoint property of re-parsing the result of geturl()
        result3 = urlparse.urlsplit(result.geturl())
        self.assertEqual(result3.geturl(), result.geturl())
        self.assertEqual(result3,          result)
        self.assertEqual(result3.scheme,   result.scheme)
        self.assertEqual(result3.netloc,   result.netloc)
        self.assertEqual(result3.path,     result.path)
        self.assertEqual(result3.query,    result.query)
        self.assertEqual(result3.fragment, result.fragment)
        self.assertEqual(result3.username, result.username)
        self.assertEqual(result3.password, result.password)
        self.assertEqual(result3.hostname, result.hostname)
        self.assertEqual(result3.port,     result.port)

    def test_qsl(self):
        for orig, expect in parse_qsl_test_cases:
            result = urlparse.parse_qsl(orig, keep_blank_values=True)
            self.assertEqual(result, expect, "Error parsing %r" % orig)
            expect_without_blanks = [v for v in expect if len(v[1])]
            result = urlparse.parse_qsl(orig, keep_blank_values=False)
            self.assertEqual(result, expect_without_blanks,
                            "Error parsing %r" % orig)

    def test_roundtrips(self):
        str_cases = [
            (u'file:///tmp/junk.txt',
             (u'file', u'', u'/tmp/junk.txt', u'', u'', u''),
             (u'file', u'', u'/tmp/junk.txt', u'', u'')),
            (u'imap://mail.python.org/mbox1',
             (u'imap', u'mail.python.org', u'/mbox1', u'', u'', u''),
             (u'imap', u'mail.python.org', u'/mbox1', u'', u'')),
            (u'mms://wms.sys.hinet.net/cts/Drama/09006251100.asf',
             (u'mms', u'wms.sys.hinet.net', u'/cts/Drama/09006251100.asf',
              u'', u'', u''),
             (u'mms', u'wms.sys.hinet.net', u'/cts/Drama/09006251100.asf',
              u'', u'')),
            (u'nfs://server/path/to/file.txt',
             (u'nfs', u'server', u'/path/to/file.txt', u'', u'', u''),
             (u'nfs', u'server', u'/path/to/file.txt', u'', u'')),
            (u'svn+ssh://svn.zope.org/repos/main/ZConfig/trunk/',
             (u'svn+ssh', u'svn.zope.org', u'/repos/main/ZConfig/trunk/',
              u'', u'', u''),
             (u'svn+ssh', u'svn.zope.org', u'/repos/main/ZConfig/trunk/',
              u'', u'')),
            (u'git+ssh://git@github.com/user/project.git',
            (u'git+ssh', u'git@github.com', u'/user/project.git',
             u'',u'',u''),
            (u'git+ssh', u'git@github.com', u'/user/project.git',
             u'', u'')),
            ]
        def _encode(t):
            return (t[0].encode('ascii'),
                    tuple(x.encode('ascii') for x in t[1]),
                    tuple(x.encode('ascii') for x in t[2]))
        bytes_cases = [_encode(x) for x in str_cases]
        for url, parsed, split in str_cases + bytes_cases:
            self.checkRoundtrips(url, parsed, split)

    def test_http_roundtrips(self):
        # urlparse.urlsplit treats 'http:' as an optimized special case,
        # so we test both 'http:' and 'https:' in all the following.
        # Three cheers for white box knowledge!
        str_cases = [
            (u'://www.python.org',
             (u'www.python.org', u'', u'', u'', u''),
             (u'www.python.org', u'', u'', u'')),
            (u'://www.python.org#abc',
             (u'www.python.org', u'', u'', u'', u'abc'),
             (u'www.python.org', u'', u'', u'abc')),
            (u'://www.python.org?q=abc',
             (u'www.python.org', u'', u'', u'q=abc', u''),
             (u'www.python.org', u'', u'q=abc', u'')),
            (u'://www.python.org/#abc',
             (u'www.python.org', u'/', u'', u'', u'abc'),
             (u'www.python.org', u'/', u'', u'abc')),
            (u'://a/b/c/d;p?q#f',
             (u'a', u'/b/c/d', u'p', u'q', u'f'),
             (u'a', u'/b/c/d;p', u'q', u'f')),
            ]
        def _encode(t):
            return (t[0].encode('ascii'),
                    tuple(x.encode('ascii') for x in t[1]),
                    tuple(x.encode('ascii') for x in t[2]))
        bytes_cases = [_encode(x) for x in str_cases]
        str_schemes = (u'http', u'https')
        bytes_schemes = (b'http', b'https')
        str_tests = str_schemes, str_cases
        bytes_tests = bytes_schemes, bytes_cases
        for schemes, test_cases in (str_tests, bytes_tests):
            for scheme in schemes:
                for url, parsed, split in test_cases:
                    url = scheme + url
                    parsed = (scheme,) + parsed
                    split = (scheme,) + split
                    self.checkRoundtrips(url, parsed, split)

    def checkJoin(self, base, relurl, expected):
        str_components = (base, relurl, expected)
        self.assertEqual(urlparse.urljoin(base, relurl), expected)
        bytes_components = baseb, relurlb, expectedb = [
                            x.encode('ascii') for x in str_components]
        self.assertEqual(urlparse.urljoin(baseb, relurlb), expectedb)

    def test_unparse_parse(self):
        str_cases = [
            u'Python', u'./Python', u'x-newscheme://foo.com/stuff', u'x://y',
            u'x:/y', u'x:/', u'/'
        ]
        bytes_cases = [x.encode('ascii') for x in str_cases]
        for u in str_cases + bytes_cases:
            self.assertEqual(urlparse.urlunsplit(urlparse.urlsplit(u)), u)
            self.assertEqual(urlparse.urlunparse(urlparse.urlparse(u)), u)

    def test_RFC1808(self):
        # "normal" cases from RFC 1808:
        self.checkJoin(RFC1808_BASE, u'g:h', u'g:h')
        self.checkJoin(RFC1808_BASE, u'g', u'http://a/b/c/g')
        self.checkJoin(RFC1808_BASE, u'./g', u'http://a/b/c/g')
        self.checkJoin(RFC1808_BASE, u'g/', u'http://a/b/c/g/')
        self.checkJoin(RFC1808_BASE, u'/g', u'http://a/g')
        self.checkJoin(RFC1808_BASE, u'//g', u'http://g')
        self.checkJoin(RFC1808_BASE, u'g?y', u'http://a/b/c/g?y')
        self.checkJoin(RFC1808_BASE, u'g?y/./x', u'http://a/b/c/g?y/./x')
        self.checkJoin(RFC1808_BASE, u'#s', u'http://a/b/c/d;p?q#s')
        self.checkJoin(RFC1808_BASE, u'g#s', u'http://a/b/c/g#s')
        self.checkJoin(RFC1808_BASE, u'g#s/./x', u'http://a/b/c/g#s/./x')
        self.checkJoin(RFC1808_BASE, u'g?y#s', u'http://a/b/c/g?y#s')
        self.checkJoin(RFC1808_BASE, u'g;x', u'http://a/b/c/g;x')
        self.checkJoin(RFC1808_BASE, u'g;x?y#s', u'http://a/b/c/g;x?y#s')
        self.checkJoin(RFC1808_BASE, u'.', u'http://a/b/c/')
        self.checkJoin(RFC1808_BASE, u'./', u'http://a/b/c/')
        self.checkJoin(RFC1808_BASE, u'..', u'http://a/b/')
        self.checkJoin(RFC1808_BASE, u'../', u'http://a/b/')
        self.checkJoin(RFC1808_BASE, u'../g', u'http://a/b/g')
        self.checkJoin(RFC1808_BASE, u'../..', u'http://a/')
        self.checkJoin(RFC1808_BASE, u'../../', u'http://a/')
        self.checkJoin(RFC1808_BASE, u'../../g', u'http://a/g')

        # "abnormal" cases from RFC 1808:
        self.checkJoin(RFC1808_BASE, u'', u'http://a/b/c/d;p?q#f')
        self.checkJoin(RFC1808_BASE, u'../../../g', u'http://a/../g')
        self.checkJoin(RFC1808_BASE, u'../../../../g', u'http://a/../../g')
        self.checkJoin(RFC1808_BASE, u'/./g', u'http://a/./g')
        self.checkJoin(RFC1808_BASE, u'/../g', u'http://a/../g')
        self.checkJoin(RFC1808_BASE, u'g.', u'http://a/b/c/g.')
        self.checkJoin(RFC1808_BASE, u'.g', u'http://a/b/c/.g')
        self.checkJoin(RFC1808_BASE, u'g..', u'http://a/b/c/g..')
        self.checkJoin(RFC1808_BASE, u'..g', u'http://a/b/c/..g')
        self.checkJoin(RFC1808_BASE, u'./../g', u'http://a/b/g')
        self.checkJoin(RFC1808_BASE, u'./g/.', u'http://a/b/c/g/')
        self.checkJoin(RFC1808_BASE, u'g/./h', u'http://a/b/c/g/h')
        self.checkJoin(RFC1808_BASE, u'g/../h', u'http://a/b/c/h')

        # RFC 1808 and RFC 1630 disagree on these (according to RFC 1808),
        # so we'll not actually run these tests (which expect 1808 behavior).
        #self.checkJoin(RFC1808_BASE, 'http:g', 'http:g')
        #self.checkJoin(RFC1808_BASE, 'http:', 'http:')

    def test_RFC2368(self):
        # Issue 11467: path that starts with a number is not parsed correctly
        self.assertEqual(urlparse.urlparse(u'mailto:1337@example.org'),
                (u'mailto', u'', u'1337@example.org', u'', u'', u''))

    def test_RFC2396(self):
        # cases from RFC 2396


        self.checkJoin(RFC2396_BASE, u'g:h', u'g:h')
        self.checkJoin(RFC2396_BASE, u'g', u'http://a/b/c/g')
        self.checkJoin(RFC2396_BASE, u'./g', u'http://a/b/c/g')
        self.checkJoin(RFC2396_BASE, u'g/', u'http://a/b/c/g/')
        self.checkJoin(RFC2396_BASE, u'/g', u'http://a/g')
        self.checkJoin(RFC2396_BASE, u'//g', u'http://g')
        self.checkJoin(RFC2396_BASE, u'g?y', u'http://a/b/c/g?y')
        self.checkJoin(RFC2396_BASE, u'#s', u'http://a/b/c/d;p?q#s')
        self.checkJoin(RFC2396_BASE, u'g#s', u'http://a/b/c/g#s')
        self.checkJoin(RFC2396_BASE, u'g?y#s', u'http://a/b/c/g?y#s')
        self.checkJoin(RFC2396_BASE, u'g;x', u'http://a/b/c/g;x')
        self.checkJoin(RFC2396_BASE, u'g;x?y#s', u'http://a/b/c/g;x?y#s')
        self.checkJoin(RFC2396_BASE, u'.', u'http://a/b/c/')
        self.checkJoin(RFC2396_BASE, u'./', u'http://a/b/c/')
        self.checkJoin(RFC2396_BASE, u'..', u'http://a/b/')
        self.checkJoin(RFC2396_BASE, u'../', u'http://a/b/')
        self.checkJoin(RFC2396_BASE, u'../g', u'http://a/b/g')
        self.checkJoin(RFC2396_BASE, u'../..', u'http://a/')
        self.checkJoin(RFC2396_BASE, u'../../', u'http://a/')
        self.checkJoin(RFC2396_BASE, u'../../g', u'http://a/g')
        self.checkJoin(RFC2396_BASE, u'', RFC2396_BASE)
        self.checkJoin(RFC2396_BASE, u'../../../g', u'http://a/../g')
        self.checkJoin(RFC2396_BASE, u'../../../../g', u'http://a/../../g')
        self.checkJoin(RFC2396_BASE, u'/./g', u'http://a/./g')
        self.checkJoin(RFC2396_BASE, u'/../g', u'http://a/../g')
        self.checkJoin(RFC2396_BASE, u'g.', u'http://a/b/c/g.')
        self.checkJoin(RFC2396_BASE, u'.g', u'http://a/b/c/.g')
        self.checkJoin(RFC2396_BASE, u'g..', u'http://a/b/c/g..')
        self.checkJoin(RFC2396_BASE, u'..g', u'http://a/b/c/..g')
        self.checkJoin(RFC2396_BASE, u'./../g', u'http://a/b/g')
        self.checkJoin(RFC2396_BASE, u'./g/.', u'http://a/b/c/g/')
        self.checkJoin(RFC2396_BASE, u'g/./h', u'http://a/b/c/g/h')
        self.checkJoin(RFC2396_BASE, u'g/../h', u'http://a/b/c/h')
        self.checkJoin(RFC2396_BASE, u'g;x=1/./y', u'http://a/b/c/g;x=1/y')
        self.checkJoin(RFC2396_BASE, u'g;x=1/../y', u'http://a/b/c/y')
        self.checkJoin(RFC2396_BASE, u'g?y/./x', u'http://a/b/c/g?y/./x')
        self.checkJoin(RFC2396_BASE, u'g?y/../x', u'http://a/b/c/g?y/../x')
        self.checkJoin(RFC2396_BASE, u'g#s/./x', u'http://a/b/c/g#s/./x')
        self.checkJoin(RFC2396_BASE, u'g#s/../x', u'http://a/b/c/g#s/../x')

    def test_RFC3986(self):
        # Test cases from RFC3986
        self.checkJoin(RFC3986_BASE, u'?y', u'http://a/b/c/d;p?y')
        self.checkJoin(RFC2396_BASE, u';x', u'http://a/b/c/;x')
        self.checkJoin(RFC3986_BASE, u'g:h', u'g:h')
        self.checkJoin(RFC3986_BASE, u'g', u'http://a/b/c/g')
        self.checkJoin(RFC3986_BASE, u'./g', u'http://a/b/c/g')
        self.checkJoin(RFC3986_BASE, u'g/', u'http://a/b/c/g/')
        self.checkJoin(RFC3986_BASE, u'/g', u'http://a/g')
        self.checkJoin(RFC3986_BASE, u'//g', u'http://g')
        self.checkJoin(RFC3986_BASE, u'?y', u'http://a/b/c/d;p?y')
        self.checkJoin(RFC3986_BASE, u'g?y', u'http://a/b/c/g?y')
        self.checkJoin(RFC3986_BASE, u'#s', u'http://a/b/c/d;p?q#s')
        self.checkJoin(RFC3986_BASE, u'g#s', u'http://a/b/c/g#s')
        self.checkJoin(RFC3986_BASE, u'g?y#s', u'http://a/b/c/g?y#s')
        self.checkJoin(RFC3986_BASE, u';x', u'http://a/b/c/;x')
        self.checkJoin(RFC3986_BASE, u'g;x', u'http://a/b/c/g;x')
        self.checkJoin(RFC3986_BASE, u'g;x?y#s', u'http://a/b/c/g;x?y#s')
        self.checkJoin(RFC3986_BASE, u'', u'http://a/b/c/d;p?q')
        self.checkJoin(RFC3986_BASE, u'.', u'http://a/b/c/')
        self.checkJoin(RFC3986_BASE, u'./', u'http://a/b/c/')
        self.checkJoin(RFC3986_BASE, u'..', u'http://a/b/')
        self.checkJoin(RFC3986_BASE, u'../', u'http://a/b/')
        self.checkJoin(RFC3986_BASE, u'../g', u'http://a/b/g')
        self.checkJoin(RFC3986_BASE, u'../..', u'http://a/')
        self.checkJoin(RFC3986_BASE, u'../../', u'http://a/')
        self.checkJoin(RFC3986_BASE, u'../../g', u'http://a/g')

        #Abnormal Examples

        # The 'abnormal scenarios' are incompatible with RFC2986 parsing
        # Tests are here for reference.

        #self.checkJoin(RFC3986_BASE, u'../../../g',u'http://a/g')
        #self.checkJoin(RFC3986_BASE, u'../../../../g',u'http://a/g')
        #self.checkJoin(RFC3986_BASE, u'/./g',u'http://a/g')
        #self.checkJoin(RFC3986_BASE, u'/../g',u'http://a/g')

        self.checkJoin(RFC3986_BASE, u'g.', u'http://a/b/c/g.')
        self.checkJoin(RFC3986_BASE, u'.g', u'http://a/b/c/.g')
        self.checkJoin(RFC3986_BASE, u'g..', u'http://a/b/c/g..')
        self.checkJoin(RFC3986_BASE, u'..g', u'http://a/b/c/..g')
        self.checkJoin(RFC3986_BASE, u'./../g', u'http://a/b/g')
        self.checkJoin(RFC3986_BASE, u'./g/.', u'http://a/b/c/g/')
        self.checkJoin(RFC3986_BASE, u'g/./h', u'http://a/b/c/g/h')
        self.checkJoin(RFC3986_BASE, u'g/../h', u'http://a/b/c/h')
        self.checkJoin(RFC3986_BASE, u'g;x=1/./y', u'http://a/b/c/g;x=1/y')
        self.checkJoin(RFC3986_BASE, u'g;x=1/../y', u'http://a/b/c/y')
        self.checkJoin(RFC3986_BASE, u'g?y/./x', u'http://a/b/c/g?y/./x')
        self.checkJoin(RFC3986_BASE, u'g?y/../x', u'http://a/b/c/g?y/../x')
        self.checkJoin(RFC3986_BASE, u'g#s/./x', u'http://a/b/c/g#s/./x')
        self.checkJoin(RFC3986_BASE, u'g#s/../x', u'http://a/b/c/g#s/../x')
        #self.checkJoin(RFC3986_BASE, u'http:g',u'http:g') # strict parser
        self.checkJoin(RFC3986_BASE, u'http:g', u'http://a/b/c/g') #relaxed parser

        # Test for issue9721
        self.checkJoin(u'http://a/b/c/de', u';x',u'http://a/b/c/;x')

    def test_urljoins(self):
        self.checkJoin(SIMPLE_BASE, u'g:h',u'g:h')
        self.checkJoin(SIMPLE_BASE, u'http:g',u'http://a/b/c/g')
        self.checkJoin(SIMPLE_BASE, u'http:',u'http://a/b/c/d')
        self.checkJoin(SIMPLE_BASE, u'g',u'http://a/b/c/g')
        self.checkJoin(SIMPLE_BASE, u'./g',u'http://a/b/c/g')
        self.checkJoin(SIMPLE_BASE, u'g/',u'http://a/b/c/g/')
        self.checkJoin(SIMPLE_BASE, u'/g',u'http://a/g')
        self.checkJoin(SIMPLE_BASE, u'//g',u'http://g')
        self.checkJoin(SIMPLE_BASE, u'?y',u'http://a/b/c/d?y')
        self.checkJoin(SIMPLE_BASE, u'g?y',u'http://a/b/c/g?y')
        self.checkJoin(SIMPLE_BASE, u'g?y/./x',u'http://a/b/c/g?y/./x')
        self.checkJoin(SIMPLE_BASE, u'.',u'http://a/b/c/')
        self.checkJoin(SIMPLE_BASE, u'./',u'http://a/b/c/')
        self.checkJoin(SIMPLE_BASE, u'..',u'http://a/b/')
        self.checkJoin(SIMPLE_BASE, u'../',u'http://a/b/')
        self.checkJoin(SIMPLE_BASE, u'../g',u'http://a/b/g')
        self.checkJoin(SIMPLE_BASE, u'../..',u'http://a/')
        self.checkJoin(SIMPLE_BASE, u'../../g',u'http://a/g')
        self.checkJoin(SIMPLE_BASE, u'../../../g',u'http://a/../g')
        self.checkJoin(SIMPLE_BASE, u'./../g',u'http://a/b/g')
        self.checkJoin(SIMPLE_BASE, u'./g/.',u'http://a/b/c/g/')
        self.checkJoin(SIMPLE_BASE, u'/./g',u'http://a/./g')
        self.checkJoin(SIMPLE_BASE, u'g/./h',u'http://a/b/c/g/h')
        self.checkJoin(SIMPLE_BASE, u'g/../h',u'http://a/b/c/h')
        self.checkJoin(SIMPLE_BASE, u'http:g',u'http://a/b/c/g')
        self.checkJoin(SIMPLE_BASE, u'http:',u'http://a/b/c/d')
        self.checkJoin(SIMPLE_BASE, u'http:?y',u'http://a/b/c/d?y')
        self.checkJoin(SIMPLE_BASE, u'http:g?y',u'http://a/b/c/g?y')
        self.checkJoin(SIMPLE_BASE, u'http:g?y/./x',u'http://a/b/c/g?y/./x')
        self.checkJoin(u'http:///', u'..',u'http:///')
        self.checkJoin(u'', u'http://a/b/c/g?y/./x',u'http://a/b/c/g?y/./x')
        self.checkJoin(u'', u'http://a/./g', u'http://a/./g')
        self.checkJoin(u'svn://pathtorepo/dir1', u'dir2', u'svn://pathtorepo/dir2')
        self.checkJoin(u'svn+ssh://pathtorepo/dir1', u'dir2', u'svn+ssh://pathtorepo/dir2')

    def test_RFC2732(self):
        str_cases = [
            (u'http://Test.python.org:5432/foo/', u'test.python.org', 5432),
            (u'http://12.34.56.78:5432/foo/', u'12.34.56.78', 5432),
            (u'http://[::1]:5432/foo/', u'::1', 5432),
            (u'http://[dead:beef::1]:5432/foo/', u'dead:beef::1', 5432),
            (u'http://[dead:beef::]:5432/foo/', u'dead:beef::', 5432),
            (u'http://[dead:beef:cafe:5417:affe:8FA3:deaf:feed]:5432/foo/',
             u'dead:beef:cafe:5417:affe:8fa3:deaf:feed', 5432),
            (u'http://[::12.34.56.78]:5432/foo/', u'::12.34.56.78', 5432),
            (u'http://[::ffff:12.34.56.78]:5432/foo/',
             u'::ffff:12.34.56.78', 5432),
            (u'http://Test.python.org/foo/', u'test.python.org', None),
            (u'http://12.34.56.78/foo/', u'12.34.56.78', None),
            (u'http://[::1]/foo/', u'::1', None),
            (u'http://[dead:beef::1]/foo/', u'dead:beef::1', None),
            (u'http://[dead:beef::]/foo/', u'dead:beef::', None),
            (u'http://[dead:beef:cafe:5417:affe:8FA3:deaf:feed]/foo/',
             u'dead:beef:cafe:5417:affe:8fa3:deaf:feed', None),
            (u'http://[::12.34.56.78]/foo/', u'::12.34.56.78', None),
            (u'http://[::ffff:12.34.56.78]/foo/',
             u'::ffff:12.34.56.78', None),
            ]
        def _encode(t):
            return t[0].encode('ascii'), t[1].encode('ascii'), t[2]
        bytes_cases = [_encode(x) for x in str_cases]
        for url, hostname, port in str_cases + bytes_cases:
            urlparsed = urlparse.urlparse(url)
            self.assertEqual((urlparsed.hostname, urlparsed.port) , (hostname, port))

        str_cases = [
                u'http://::12.34.56.78]/',
                u'http://[::1/foo/',
                u'ftp://[::1/foo/bad]/bad',
                u'http://[::1/foo/bad]/bad',
                u'http://[::ffff:12.34.56.78']
        bytes_cases = [x.encode('ascii') for x in str_cases]
        for invalid_url in str_cases + bytes_cases:
            self.assertRaises(ValueError, urlparse.urlparse, invalid_url)

    def test_urldefrag(self):
        str_cases = [
            (u'http://python.org#frag', u'http://python.org', u'frag'),
            (u'http://python.org', u'http://python.org', u''),
            (u'http://python.org/#frag', u'http://python.org/', u'frag'),
            (u'http://python.org/', u'http://python.org/', u''),
            (u'http://python.org/?q#frag', u'http://python.org/?q', u'frag'),
            (u'http://python.org/?q', u'http://python.org/?q', u''),
            (u'http://python.org/p#frag', u'http://python.org/p', u'frag'),
            (u'http://python.org/p?q', u'http://python.org/p?q', u''),
            (RFC1808_BASE, u'http://a/b/c/d;p?q', u'f'),
            (RFC2396_BASE, u'http://a/b/c/d;p?q', u''),
        ]
        def _encode(t):
            return type(t)(x.encode('ascii') for x in t)
        bytes_cases = [_encode(x) for x in str_cases]
        for url, defrag, frag in str_cases + bytes_cases:
            result = urlparse.urldefrag(url)
            self.assertEqual(result.geturl(), url)
            self.assertEqual(result, (defrag, frag))
            self.assertEqual(result.url, defrag)
            self.assertEqual(result.fragment, frag)

    def test_urlsplit_attributes(self):
        url = u"HTTP://WWW.PYTHON.ORG/doc/#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, u"http")
        self.assertEqual(p.netloc, u"WWW.PYTHON.ORG")
        self.assertEqual(p.path, u"/doc/")
        self.assertEqual(p.query, u"")
        self.assertEqual(p.fragment, u"frag")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, u"www.python.org")
        self.assertEqual(p.port, None)
        # geturl() won't return exactly the original URL in this case
        # since the scheme is always case-normalized
        # We handle this by ignoring the first 4 characters of the URL
        self.assertEqual(p.geturl()[4:], url[4:])

        url = u"http://User:Pass@www.python.org:080/doc/?query=yes#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, u"http")
        self.assertEqual(p.netloc, u"User:Pass@www.python.org:080")
        self.assertEqual(p.path, u"/doc/")
        self.assertEqual(p.query, u"query=yes")
        self.assertEqual(p.fragment, u"frag")
        self.assertEqual(p.username, u"User")
        self.assertEqual(p.password, u"Pass")
        self.assertEqual(p.hostname, u"www.python.org")
        self.assertEqual(p.port, 80)
        self.assertEqual(p.geturl(), url)

        # Addressing issue1698, which suggests Username can contain
        # "@" characters.  Though not RFC compliant, many ftp sites allow
        # and request email addresses as usernames.

        url = u"http://User@example.com:Pass@www.python.org:080/doc/?query=yes#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, u"http")
        self.assertEqual(p.netloc, u"User@example.com:Pass@www.python.org:080")
        self.assertEqual(p.path, u"/doc/")
        self.assertEqual(p.query, u"query=yes")
        self.assertEqual(p.fragment, u"frag")
        self.assertEqual(p.username, u"User@example.com")
        self.assertEqual(p.password, u"Pass")
        self.assertEqual(p.hostname, u"www.python.org")
        self.assertEqual(p.port, 80)
        self.assertEqual(p.geturl(), url)

        # And check them all again, only with bytes this time
        url = b"HTTP://WWW.PYTHON.ORG/doc/#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, b"http")
        self.assertEqual(p.netloc, b"WWW.PYTHON.ORG")
        self.assertEqual(p.path, b"/doc/")
        self.assertEqual(p.query, b"")
        self.assertEqual(p.fragment, b"frag")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, b"www.python.org")
        self.assertEqual(p.port, None)
        self.assertEqual(p.geturl()[4:], url[4:])

        url = b"http://User:Pass@www.python.org:080/doc/?query=yes#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, b"http")
        self.assertEqual(p.netloc, b"User:Pass@www.python.org:080")
        self.assertEqual(p.path, b"/doc/")
        self.assertEqual(p.query, b"query=yes")
        self.assertEqual(p.fragment, b"frag")
        self.assertEqual(p.username, b"User")
        self.assertEqual(p.password, b"Pass")
        self.assertEqual(p.hostname, b"www.python.org")
        self.assertEqual(p.port, 80)
        self.assertEqual(p.geturl(), url)

        url = b"http://User@example.com:Pass@www.python.org:080/doc/?query=yes#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.scheme, b"http")
        self.assertEqual(p.netloc, b"User@example.com:Pass@www.python.org:080")
        self.assertEqual(p.path, b"/doc/")
        self.assertEqual(p.query, b"query=yes")
        self.assertEqual(p.fragment, b"frag")
        self.assertEqual(p.username, b"User@example.com")
        self.assertEqual(p.password, b"Pass")
        self.assertEqual(p.hostname, b"www.python.org")
        self.assertEqual(p.port, 80)
        self.assertEqual(p.geturl(), url)

        # Verify an illegal port is returned as None
        url = b"HTTP://WWW.PYTHON.ORG:65536/doc/#frag"
        p = urlparse.urlsplit(url)
        self.assertEqual(p.port, None)

    def test_attributes_bad_port(self):
        """Check handling of non-integer ports."""
        p = urlparse.urlsplit(u"http://www.example.net:foo")
        self.assertEqual(p.netloc, u"www.example.net:foo")
        self.assertRaises(ValueError, lambda: p.port)

        p = urlparse.urlparse(u"http://www.example.net:foo")
        self.assertEqual(p.netloc, u"www.example.net:foo")
        self.assertRaises(ValueError, lambda: p.port)

        # Once again, repeat ourselves to test bytes
        p = urlparse.urlsplit(b"http://www.example.net:foo")
        self.assertEqual(p.netloc, b"www.example.net:foo")
        self.assertRaises(ValueError, lambda: p.port)

        p = urlparse.urlparse(b"http://www.example.net:foo")
        self.assertEqual(p.netloc, b"www.example.net:foo")
        self.assertRaises(ValueError, lambda: p.port)

    def test_attributes_without_netloc(self):
        # This example is straight from RFC 3261.  It looks like it
        # should allow the username, hostname, and port to be filled
        # in, but doesn't.  Since it's a URI and doesn't use the
        # scheme://netloc syntax, the netloc and related attributes
        # should be left empty.
        uri = u"sip:alice@atlanta.com;maddr=239.255.255.1;ttl=15"
        p = urlparse.urlsplit(uri)
        self.assertEqual(p.netloc, u"")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, None)
        self.assertEqual(p.port, None)
        self.assertEqual(p.geturl(), uri)

        p = urlparse.urlparse(uri)
        self.assertEqual(p.netloc, u"")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, None)
        self.assertEqual(p.port, None)
        self.assertEqual(p.geturl(), uri)

        # You guessed it, repeating the test with bytes input
        uri = b"sip:alice@atlanta.com;maddr=239.255.255.1;ttl=15"
        p = urlparse.urlsplit(uri)
        self.assertEqual(p.netloc, b"")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, None)
        self.assertEqual(p.port, None)
        self.assertEqual(p.geturl(), uri)

        p = urlparse.urlparse(uri)
        self.assertEqual(p.netloc, b"")
        self.assertEqual(p.username, None)
        self.assertEqual(p.password, None)
        self.assertEqual(p.hostname, None)
        self.assertEqual(p.port, None)
        self.assertEqual(p.geturl(), uri)

    def test_noslash(self):
        # Issue 1637: http://foo.com?query is legal
        self.assertEqual(urlparse.urlparse("http://example.com?blahblah=/foo"),
                         (u'http', u'example.com', u'', u'', u'blahblah=/foo', u''))
        self.assertEqual(urlparse.urlparse(b"http://example.com?blahblah=/foo"),
                         (b'http', b'example.com', b'', b'', b'blahblah=/foo', b''))

    def test_withoutscheme(self):
        # Test urlparse without scheme
        # Issue 754016: urlparse goes wrong with IP:port without scheme
        # RFC 1808 specifies that netloc should start with //, urlparse expects
        # the same, otherwise it classifies the portion of url as path.
        self.assertEqual(urlparse.urlparse("path"),
                (u'',u'',u'path',u'',u'',u''))
        self.assertEqual(urlparse.urlparse("//www.python.org:80"),
                (u'',u'www.python.org:80',u'',u'',u'',u''))
        self.assertEqual(urlparse.urlparse("http://www.python.org:80"),
                (u'http',u'www.python.org:80',u'',u'',u'',u''))
        # Repeat for bytes input
        self.assertEqual(urlparse.urlparse(b"path"),
                (b'',b'',b'path',b'',b'',b''))
        self.assertEqual(urlparse.urlparse(b"//www.python.org:80"),
                (b'',b'www.python.org:80',b'',b'',b'',b''))
        self.assertEqual(urlparse.urlparse(b"http://www.python.org:80"),
                (b'http',b'www.python.org:80',b'',b'',b'',b''))

    def test_portseparator(self):
        # Issue 754016 makes changes for port separator ':' from scheme separator
        self.assertEqual(urlparse.urlparse("path:80"),
                (u'',u'',u'path:80',u'',u'',u''))
        self.assertEqual(urlparse.urlparse("http:"),(u'http',u'',u'',u'',u'',u''))
        self.assertEqual(urlparse.urlparse("https:"),(u'https',u'',u'',u'',u'',u''))
        self.assertEqual(urlparse.urlparse("http://www.python.org:80"),
                (u'http',u'www.python.org:80',u'',u'',u'',u''))
        # As usual, need to check bytes input as well
        self.assertEqual(urlparse.urlparse(b"path:80"),
                (b'',b'',b'path:80',b'',b'',b''))
        self.assertEqual(urlparse.urlparse(b"http:"),(b'http',b'',b'',b'',b'',b''))
        self.assertEqual(urlparse.urlparse(b"https:"),(b'https',b'',b'',b'',b'',b''))
        self.assertEqual(urlparse.urlparse(b"http://www.python.org:80"),
                (b'http',b'www.python.org:80',b'',b'',b'',b''))

    def test_usingsys(self):
        # Issue 3314: sys module is used in the error
        self.assertRaises(TypeError, urlparse.urlencode, "foo")

    def test_anyscheme(self):
        # Issue 7904: s3://foo.com/stuff has netloc "foo.com".
        self.assertEqual(urlparse.urlparse("s3://foo.com/stuff"),
                         (u's3', u'foo.com', u'/stuff', u'', u'', u''))
        self.assertEqual(urlparse.urlparse("x-newscheme://foo.com/stuff"),
                         (u'x-newscheme', u'foo.com', u'/stuff', u'', u'', u''))
        self.assertEqual(urlparse.urlparse("x-newscheme://foo.com/stuff?query#fragment"),
                         (u'x-newscheme', u'foo.com', u'/stuff', u'', u'query', u'fragment'))
        self.assertEqual(urlparse.urlparse("x-newscheme://foo.com/stuff?query"),
                         (u'x-newscheme', u'foo.com', u'/stuff', u'', u'query', u''))

        # And for bytes...
        self.assertEqual(urlparse.urlparse(b"s3://foo.com/stuff"),
                         (b's3', b'foo.com', b'/stuff', b'', b'', b''))
        self.assertEqual(urlparse.urlparse(b"x-newscheme://foo.com/stuff"),
                         (b'x-newscheme', b'foo.com', b'/stuff', b'', b'', b''))
        self.assertEqual(urlparse.urlparse(b"x-newscheme://foo.com/stuff?query#fragment"),
                         (b'x-newscheme', b'foo.com', b'/stuff', b'', b'query', b'fragment'))
        self.assertEqual(urlparse.urlparse(b"x-newscheme://foo.com/stuff?query"),
                         (b'x-newscheme', b'foo.com', b'/stuff', b'', b'query', b''))

    def test_mixed_types_rejected(self):
        # Several functions that process either strings or ASCII encoded bytes
        # accept multiple arguments. Check they reject mixed type input
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlparse(u"www.python.org", b"http")
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlparse(b"www.python.org", u"http")
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlsplit(u"www.python.org", b"http")
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlsplit(b"www.python.org", u"http")
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlunparse(( b"http", u"www.python.org",u"",u"",u"",u""))
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlunparse((u"http", b"www.python.org",u"",u"",u"",u""))
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlunsplit((b"http", u"www.python.org",u"",u"",u""))
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urlunsplit((u"http", b"www.python.org",u"",u"",u""))
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urljoin(u"http://python.org", b"http://python.org")
        with self.assertRaisesRegex(TypeError, "Cannot mix str"):
            urlparse.urljoin(b"http://python.org", u"http://python.org")

    def _check_result_type(self, str_type):
        num_args = len(str_type._fields)
        bytes_type = str_type._encoded_counterpart
        self.assertIs(bytes_type._decoded_counterpart, str_type)
        str_args = (u'',) * num_args
        bytes_args = (b'',) * num_args
        str_result = str_type(*str_args)
        bytes_result = bytes_type(*bytes_args)
        encoding = 'ascii'
        errors = 'strict'
        self.assertEqual(str_result, str_args)
        self.assertEqual(bytes_result.decode(), str_args)
        self.assertEqual(bytes_result.decode(), str_result)
        self.assertEqual(bytes_result.decode(encoding), str_args)
        self.assertEqual(bytes_result.decode(encoding), str_result)
        self.assertEqual(bytes_result.decode(encoding, errors), str_args)
        self.assertEqual(bytes_result.decode(encoding, errors), str_result)
        self.assertEqual(bytes_result, bytes_args)
        self.assertEqual(str_result.encode(), bytes_args)
        self.assertEqual(str_result.encode(), bytes_result)
        self.assertEqual(str_result.encode(encoding), bytes_args)
        self.assertEqual(str_result.encode(encoding), bytes_result)
        self.assertEqual(str_result.encode(encoding, errors), bytes_args)
        self.assertEqual(str_result.encode(encoding, errors), bytes_result)

    def test_result_pairs(self):
        # Check encoding and decoding between result pairs
        result_types = [
          urlparse.DefragResult,
          urlparse.SplitResult,
          urlparse.ParseResult,
        ]
        for result_type in result_types:
            self._check_result_type(result_type)

    def test_parse_qs_encoding(self):
        result = urlparse.parse_qs(u"key=\u0141%E9", encoding="latin-1")
        self.assertEqual(result, {u'key': [u'\u0141\xE9']})
        result = urlparse.parse_qs(u"key=\u0141%C3%A9", encoding="utf-8")
        self.assertEqual(result, {u'key': [u'\u0141\xE9']})
        result = urlparse.parse_qs(u"key=\u0141%C3%A9", encoding="ascii")
        self.assertEqual(result, {u'key': [u'\u0141\ufffd\ufffd']})
        result = urlparse.parse_qs(u"key=\u0141%E9-", encoding="ascii")
        self.assertEqual(result, {u'key': [u'\u0141\ufffd-']})
        result = urlparse.parse_qs(u"key=\u0141%E9-", encoding="ascii",
                                                          errors="ignore")
        self.assertEqual(result, {u'key': [u'\u0141-']})

    def test_parse_qsl_encoding(self):
        result = urlparse.parse_qsl(u"key=\u0141%E9", encoding="latin-1")
        self.assertEqual(result, [(u'key', u'\u0141\xE9')])
        result = urlparse.parse_qsl(u"key=\u0141%C3%A9", encoding="utf-8")
        self.assertEqual(result, [(u'key', u'\u0141\xE9')])
        result = urlparse.parse_qsl(u"key=\u0141%C3%A9", encoding="ascii")
        self.assertEqual(result, [(u'key', u'\u0141\ufffd\ufffd')])
        result = urlparse.parse_qsl(u"key=\u0141%E9-", encoding="ascii")
        self.assertEqual(result, [(u'key', u'\u0141\ufffd-')])
        result = urlparse.parse_qsl(u"key=\u0141%E9-", encoding="ascii",
                                                          errors="ignore")
        self.assertEqual(result, [(u'key', u'\u0141-')])

    def test_splitnport(self):
        # Normal cases are exercised by other tests; ensure that we also
        # catch cases with no port specified. (testcase ensuring coverage)
        result = urlparse.splitnport(u'parrot:88')
        self.assertEqual(result, (u'parrot', 88))
        result = urlparse.splitnport(u'parrot')
        self.assertEqual(result, (u'parrot', -1))
        result = urlparse.splitnport(u'parrot', 55)
        self.assertEqual(result, (u'parrot', 55))
        result = urlparse.splitnport(u'parrot:')
        self.assertEqual(result, (u'parrot', None))

    def test_splitquery(self):
        # Normal cases are exercised by other tests; ensure that we also
        # catch cases with no port specified (testcase ensuring coverage)
        result = urlparse.splitquery(u'http://python.org/fake?foo=bar')
        self.assertEqual(result, (u'http://python.org/fake', u'foo=bar'))
        result = urlparse.splitquery(u'http://python.org/fake?foo=bar?')
        self.assertEqual(result, (u'http://python.org/fake?foo=bar', u''))
        result = urlparse.splitquery(u'http://python.org/fake')
        self.assertEqual(result, (u'http://python.org/fake', None))

    def test_splitvalue(self):
        # Normal cases are exercised by other tests; test pathological cases
        # with no key/value pairs. (testcase ensuring coverage)
        result = urlparse.splitvalue(u'foo=bar')
        self.assertEqual(result, (u'foo', u'bar'))
        result = urlparse.splitvalue(u'foo=')
        self.assertEqual(result, (u'foo', u''))
        result = urlparse.splitvalue(u'foobar')
        self.assertEqual(result, (u'foobar', None))

    def test_to_bytes(self):
        result = urlparse.to_bytes(u'http://www.python.org')
        self.assertEqual(result, u'http://www.python.org')
        self.assertRaises(UnicodeError, urlparse.to_bytes,
                          u'http://www.python.org/medi\u00e6val')

    def test_urlencode_sequences(self):
        # Other tests incidentally urlencode things; test non-covered cases:
        # Sequence and object values.
        result = urlparse.urlencode({u'a': [1, 2], u'b': (3, 4, 5)}, True)
        # we cannot rely on ordering here
        assert set(result.split(u'&')) == set([u'a=1', u'a=2', u'b=3', u'b=4', u'b=5'])

        class Trivial(object):
            if six.PY3:
                def __str__(self):
                    return u'trivial'
            else:
                def __str__(self):
                    return b'trivial'

                def __unicode__(self):
                    return u'trivial'

        result = urlparse.urlencode({u'a': Trivial()}, True)
        self.assertEqual(result, u'a=trivial')

    def test_quote_from_bytes(self):
        self.assertRaises(TypeError, urlparse.quote_from_bytes, u'foo')
        result = urlparse.quote_from_bytes(b'archaeological arcana')
        self.assertEqual(result, u'archaeological%20arcana')
        result = urlparse.quote_from_bytes(b'')
        self.assertEqual(result, u'')

        result = urlparse.quote_from_bytes(bytearray(b'archaeological arcana'))
        self.assertEqual(result, u'archaeological%20arcana')
        result = urlparse.quote_from_bytes(bytearray())
        self.assertEqual(result, u'')

    def test_unquote_to_bytes(self):
        result = urlparse.unquote_to_bytes(u'abc%20def')
        self.assertEqual(result, b'abc def')
        result = urlparse.unquote_to_bytes(u'')
        self.assertEqual(result, b'')

    def test_unquote_to_bytes_unsafe(self):
        result = urlparse.unquote_to_bytes(u'abc%20d%21ef', unsafe=b'!')
        self.assertEqual(result, b'abc d%21ef')

    def test_quote_errors(self):
        self.assertRaises(TypeError, urlparse.quote, b'foo',
                          encoding='utf-8')
        self.assertRaises(TypeError, urlparse.quote, b'foo', errors='strict')

    def test_issue14072(self):
        p1 = urlparse.urlsplit(u'tel:+31-641044153')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'+31-641044153')
        p2 = urlparse.urlsplit(u'tel:+31641044153')
        self.assertEqual(p2.scheme, u'tel')
        self.assertEqual(p2.path, u'+31641044153')
        # assert the behavior for urlparse
        p1 = urlparse.urlparse(u'tel:+31-641044153')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'+31-641044153')
        p2 = urlparse.urlparse(u'tel:+31641044153')
        self.assertEqual(p2.scheme, u'tel')
        self.assertEqual(p2.path, u'+31641044153')

    def test_telurl_params(self):
        p1 = urlparse.urlparse(u'tel:123-4;phone-context=+1-650-516')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'123-4')
        self.assertEqual(p1.params, u'phone-context=+1-650-516')

        p1 = urlparse.urlparse(u'tel:+1-201-555-0123')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'+1-201-555-0123')
        self.assertEqual(p1.params, u'')

        p1 = urlparse.urlparse(u'tel:7042;phone-context=example.com')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'7042')
        self.assertEqual(p1.params, u'phone-context=example.com')

        p1 = urlparse.urlparse(u'tel:863-1234;phone-context=+1-914-555')
        self.assertEqual(p1.scheme, u'tel')
        self.assertEqual(p1.path, u'863-1234')
        self.assertEqual(p1.params, u'phone-context=+1-914-555')

    def test_unwrap(self):
        url = urlparse.unwrap(u'<URL:type://host/path>')
        self.assertEqual(url, u'type://host/path')

    def test_Quoter_repr(self):
        quoter = urlparse.Quoter(b'')
        self.assertIn(u'Quoter', repr(quoter))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(UrlParseTestCase))
    return suite
