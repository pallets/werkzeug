import base64
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from werkzeug import datastructures
from werkzeug import http
from werkzeug._internal import _wsgi_encoding_dance
from werkzeug.test import create_environ


class TestHTTPUtility:
    def test_accept(self):
        a = http.parse_accept_header("en-us,ru;q=0.5")
        assert list(a.values()) == ["en-us", "ru"]
        assert a.best == "en-us"
        assert a.find("ru") == 1
        pytest.raises(ValueError, a.index, "de")
        assert a.to_header() == "en-us,ru;q=0.5"

    def test_mime_accept(self):
        a = http.parse_accept_header(
            "text/xml,application/xml,"
            "application/xhtml+xml,"
            "application/foo;quiet=no; bar=baz;q=0.6,"
            "text/html;q=0.9,text/plain;q=0.8,"
            "image/png,*/*;q=0.5",
            datastructures.MIMEAccept,
        )
        pytest.raises(ValueError, lambda: a["missing"])
        assert a["image/png"] == 1
        assert a["text/plain"] == 0.8
        assert a["foo/bar"] == 0.5
        assert a["application/foo;quiet=no; bar=baz"] == 0.6
        assert a[a.find("foo/bar")] == ("*/*", 0.5)

    def test_accept_matches(self):
        a = http.parse_accept_header(
            "text/xml,application/xml,application/xhtml+xml,"
            "text/html;q=0.9,text/plain;q=0.8,"
            "image/png",
            datastructures.MIMEAccept,
        )
        assert (
            a.best_match(["text/html", "application/xhtml+xml"])
            == "application/xhtml+xml"
        )
        assert a.best_match(["text/html"]) == "text/html"
        assert a.best_match(["foo/bar"]) is None
        assert a.best_match(["foo/bar", "bar/foo"], default="foo/bar") == "foo/bar"
        assert a.best_match(["application/xml", "text/xml"]) == "application/xml"

    def test_accept_mime_specificity(self):
        a = http.parse_accept_header(
            "text/*, text/html, text/html;level=1, */*", datastructures.MIMEAccept
        )
        assert a.best_match(["text/html; version=1", "text/html"]) == "text/html"
        assert a.best_match(["text/html", "text/html; level=1"]) == "text/html; level=1"

    def test_charset_accept(self):
        a = http.parse_accept_header(
            "ISO-8859-1,utf-8;q=0.7,*;q=0.7", datastructures.CharsetAccept
        )
        assert a["iso-8859-1"] == a["iso8859-1"]
        assert a["iso-8859-1"] == 1
        assert a["UTF8"] == 0.7
        assert a["ebcdic"] == 0.7

    def test_language_accept(self):
        a = http.parse_accept_header(
            "de-AT,de;q=0.8,en;q=0.5", datastructures.LanguageAccept
        )
        assert a.best == "de-AT"
        assert "de_AT" in a
        assert "en" in a
        assert a["de-at"] == 1
        assert a["en"] == 0.5

    def test_set_header(self):
        hs = http.parse_set_header('foo, Bar, "Blah baz", Hehe')
        assert "blah baz" in hs
        assert "foobar" not in hs
        assert "foo" in hs
        assert list(hs) == ["foo", "Bar", "Blah baz", "Hehe"]
        hs.add("Foo")
        assert hs.to_header() == 'foo, Bar, "Blah baz", Hehe'

    def test_list_header(self):
        hl = http.parse_list_header("foo baz, blah")
        assert hl == ["foo baz", "blah"]

    def test_dict_header(self):
        d = http.parse_dict_header('foo="bar baz", blah=42')
        assert d == {"foo": "bar baz", "blah": "42"}

    def test_cache_control_header(self):
        cc = http.parse_cache_control_header("max-age=0, no-cache")
        assert cc.max_age == 0
        assert cc.no_cache
        cc = http.parse_cache_control_header(
            'private, community="UCI"', None, datastructures.ResponseCacheControl
        )
        assert cc.private
        assert cc["community"] == "UCI"

        c = datastructures.ResponseCacheControl()
        assert c.no_cache is None
        assert c.private is None
        c.no_cache = True
        assert c.no_cache == "*"
        c.private = True
        assert c.private == "*"
        del c.private
        assert c.private is None
        assert c.to_header() == "no-cache"

    def test_csp_header(self):
        csp = http.parse_csp_header(
            "default-src 'self'; script-src 'unsafe-inline' *; img-src"
        )
        assert csp.default_src == "'self'"
        assert csp.script_src == "'unsafe-inline' *"
        assert csp.img_src is None

    def test_authorization_header(self):
        a = http.parse_authorization_header("Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==")
        assert a.type == "basic"
        assert a.username == "Aladdin"
        assert a.password == "open sesame"

        a = http.parse_authorization_header(
            "Basic 0YDRg9GB0YHQutC40IE60JHRg9C60LLRiw=="
        )
        assert a.type == "basic"
        assert a.username == "русскиЁ"
        assert a.password == "Буквы"

        a = http.parse_authorization_header("Basic 5pmu6YCa6K+dOuS4reaWhw==")
        assert a.type == "basic"
        assert a.username == "普通话"
        assert a.password == "中文"

        a = http.parse_authorization_header(
            '''Digest username="Mufasa",
            realm="testrealm@host.invalid",
            nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
            uri="/dir/index.html",
            qop=auth,
            nc=00000001,
            cnonce="0a4f113b",
            response="6629fae49393a05397450978507c4ef1",
            opaque="5ccc069c403ebaf9f0171e9517f40e41"'''
        )
        assert a.type == "digest"
        assert a.username == "Mufasa"
        assert a.realm == "testrealm@host.invalid"
        assert a.nonce == "dcd98b7102dd2f0e8b11d0f600bfb0c093"
        assert a.uri == "/dir/index.html"
        assert a.qop == "auth"
        assert a.nc == "00000001"
        assert a.cnonce == "0a4f113b"
        assert a.response == "6629fae49393a05397450978507c4ef1"
        assert a.opaque == "5ccc069c403ebaf9f0171e9517f40e41"

        a = http.parse_authorization_header(
            '''Digest username="Mufasa",
            realm="testrealm@host.invalid",
            nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
            uri="/dir/index.html",
            response="e257afa1414a3340d93d30955171dd0e",
            opaque="5ccc069c403ebaf9f0171e9517f40e41"'''
        )
        assert a.type == "digest"
        assert a.username == "Mufasa"
        assert a.realm == "testrealm@host.invalid"
        assert a.nonce == "dcd98b7102dd2f0e8b11d0f600bfb0c093"
        assert a.uri == "/dir/index.html"
        assert a.response == "e257afa1414a3340d93d30955171dd0e"
        assert a.opaque == "5ccc069c403ebaf9f0171e9517f40e41"

        assert http.parse_authorization_header("") is None
        assert http.parse_authorization_header(None) is None
        assert http.parse_authorization_header("foo") is None

    def test_bad_authorization_header_encoding(self):
        """If the base64 encoded bytes can't be decoded as UTF-8"""
        content = base64.b64encode(b"\xffser:pass").decode()
        assert http.parse_authorization_header(f"Basic {content}") is None

    def test_www_authenticate_header(self):
        wa = http.parse_www_authenticate_header('Basic realm="WallyWorld"')
        assert wa.type == "basic"
        assert wa.realm == "WallyWorld"
        wa.realm = "Foo Bar"
        assert wa.to_header() == 'Basic realm="Foo Bar"'

        wa = http.parse_www_authenticate_header(
            '''Digest
            realm="testrealm@host.com",
            qop="auth,auth-int",
            nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
            opaque="5ccc069c403ebaf9f0171e9517f40e41"'''
        )
        assert wa.type == "digest"
        assert wa.realm == "testrealm@host.com"
        assert "auth" in wa.qop
        assert "auth-int" in wa.qop
        assert wa.nonce == "dcd98b7102dd2f0e8b11d0f600bfb0c093"
        assert wa.opaque == "5ccc069c403ebaf9f0171e9517f40e41"

        wa = http.parse_www_authenticate_header("broken")
        assert wa.type == "broken"

        assert not http.parse_www_authenticate_header("").type
        assert not http.parse_www_authenticate_header("")

    def test_etags(self):
        assert http.quote_etag("foo") == '"foo"'
        assert http.quote_etag("foo", True) == 'W/"foo"'
        assert http.unquote_etag('"foo"') == ("foo", False)
        assert http.unquote_etag('W/"foo"') == ("foo", True)
        es = http.parse_etags('"foo", "bar", W/"baz", blar')
        assert sorted(es) == ["bar", "blar", "foo"]
        assert "foo" in es
        assert "baz" not in es
        assert es.contains_weak("baz")
        assert "blar" in es
        assert es.contains_raw('W/"baz"')
        assert es.contains_raw('"foo"')
        assert sorted(es.to_header().split(", ")) == [
            '"bar"',
            '"blar"',
            '"foo"',
            'W/"baz"',
        ]

    def test_etags_nonzero(self):
        etags = http.parse_etags('W/"foo"')
        assert bool(etags)
        assert etags.contains_raw('W/"foo"')

    def test_remove_entity_headers(self):
        now = http.http_date()
        headers1 = [
            ("Date", now),
            ("Content-Type", "text/html"),
            ("Content-Length", "0"),
        ]
        headers2 = datastructures.Headers(headers1)

        http.remove_entity_headers(headers1)
        assert headers1 == [("Date", now)]

        http.remove_entity_headers(headers2)
        assert headers2 == datastructures.Headers([("Date", now)])

    def test_remove_hop_by_hop_headers(self):
        headers1 = [("Connection", "closed"), ("Foo", "bar"), ("Keep-Alive", "wtf")]
        headers2 = datastructures.Headers(headers1)

        http.remove_hop_by_hop_headers(headers1)
        assert headers1 == [("Foo", "bar")]

        http.remove_hop_by_hop_headers(headers2)
        assert headers2 == datastructures.Headers([("Foo", "bar")])

    def test_parse_options_header(self):
        assert http.parse_options_header(None) == ("", {})
        assert http.parse_options_header("") == ("", {})
        assert http.parse_options_header(r'something; foo="other\"thing"') == (
            "something",
            {"foo": 'other"thing'},
        )
        assert http.parse_options_header(r'something; foo="other\"thing"; meh=42') == (
            "something",
            {"foo": 'other"thing', "meh": "42"},
        )
        assert http.parse_options_header(
            r'something; foo="other\"thing"; meh=42; bleh'
        ) == ("something", {"foo": 'other"thing', "meh": "42", "bleh": None})
        assert http.parse_options_header(
            'something; foo="other;thing"; meh=42; bleh'
        ) == ("something", {"foo": "other;thing", "meh": "42", "bleh": None})
        assert http.parse_options_header('something; foo="otherthing"; meh=; bleh') == (
            "something",
            {"foo": "otherthing", "meh": None, "bleh": None},
        )
        # Issue #404
        assert http.parse_options_header(
            'multipart/form-data; name="foo bar"; filename="bar foo"'
        ) == ("multipart/form-data", {"name": "foo bar", "filename": "bar foo"})
        # Examples from RFC
        assert http.parse_options_header("audio/*; q=0.2, audio/basic") == (
            "audio/*",
            {"q": "0.2"},
        )
        assert http.parse_options_header(
            "audio/*; q=0.2, audio/basic", multiple=True
        ) == ("audio/*", {"q": "0.2"}, "audio/basic", {})
        assert http.parse_options_header(
            "text/plain; q=0.5, text/html\n        text/x-dvi; q=0.8, text/x-c",
            multiple=True,
        ) == (
            "text/plain",
            {"q": "0.5"},
            "text/html",
            {},
            "text/x-dvi",
            {"q": "0.8"},
            "text/x-c",
            {},
        )
        assert http.parse_options_header(
            "text/plain; q=0.5, text/html\n        text/x-dvi; q=0.8, text/x-c"
        ) == ("text/plain", {"q": "0.5"})
        # Issue #932
        assert http.parse_options_header(
            "form-data; name=\"a_file\"; filename*=UTF-8''"
            '"%c2%a3%20and%20%e2%82%ac%20rates"'
        ) == ("form-data", {"name": "a_file", "filename": "\xa3 and \u20ac rates"})
        assert http.parse_options_header(
            "form-data; name*=UTF-8''\"%C5%AAn%C4%ADc%C5%8Dde%CC%BD\"; "
            'filename="some_file.txt"'
        ) == (
            "form-data",
            {"name": "\u016an\u012dc\u014dde\u033d", "filename": "some_file.txt"},
        )

    def test_parse_options_header_value_with_quotes(self):
        assert http.parse_options_header(
            'form-data; name="file"; filename="t\'es\'t.txt"'
        ) == ("form-data", {"name": "file", "filename": "t'es't.txt"})
        assert http.parse_options_header(
            "form-data; name=\"file\"; filename*=UTF-8''\"'🐍'.txt\""
        ) == ("form-data", {"name": "file", "filename": "'🐍'.txt"})

    def test_parse_options_header_broken_values(self):
        # Issue #995
        assert http.parse_options_header(" ") == ("", {})
        assert http.parse_options_header(" , ") == ("", {})
        assert http.parse_options_header(" ; ") == ("", {})
        assert http.parse_options_header(" ,; ") == ("", {})
        assert http.parse_options_header(" , a ") == ("", {})
        assert http.parse_options_header(" ; a ") == ("", {})

    def test_dump_options_header(self):
        assert http.dump_options_header("foo", {"bar": 42}) == "foo; bar=42"
        assert http.dump_options_header("foo", {"bar": 42, "fizz": None}) in (
            "foo; bar=42; fizz",
            "foo; fizz; bar=42",
        )

    def test_dump_header(self):
        assert http.dump_header([1, 2, 3]) == "1, 2, 3"
        assert http.dump_header([1, 2, 3], allow_token=False) == '"1", "2", "3"'
        assert http.dump_header({"foo": "bar"}, allow_token=False) == 'foo="bar"'
        assert http.dump_header({"foo": "bar"}) == "foo=bar"

    def test_is_resource_modified(self):
        env = create_environ()

        # any method is allowed
        env["REQUEST_METHOD"] = "POST"
        assert http.is_resource_modified(env, etag="testing")
        env["REQUEST_METHOD"] = "GET"

        # etagify from data
        pytest.raises(TypeError, http.is_resource_modified, env, data="42", etag="23")
        env["HTTP_IF_NONE_MATCH"] = http.generate_etag(b"awesome")
        assert not http.is_resource_modified(env, data=b"awesome")

        env["HTTP_IF_MODIFIED_SINCE"] = http.http_date(datetime(2008, 1, 1, 12, 30))
        assert not http.is_resource_modified(
            env, last_modified=datetime(2008, 1, 1, 12, 00)
        )
        assert http.is_resource_modified(
            env, last_modified=datetime(2008, 1, 1, 13, 00)
        )

    def test_is_resource_modified_for_range_requests(self):
        env = create_environ()

        env["HTTP_IF_MODIFIED_SINCE"] = http.http_date(datetime(2008, 1, 1, 12, 30))
        env["HTTP_IF_RANGE"] = http.generate_etag(b"awesome_if_range")
        # Range header not present, so If-Range should be ignored
        assert not http.is_resource_modified(
            env,
            data=b"not_the_same",
            ignore_if_range=False,
            last_modified=datetime(2008, 1, 1, 12, 30),
        )

        env["HTTP_RANGE"] = ""
        assert not http.is_resource_modified(
            env, data=b"awesome_if_range", ignore_if_range=False
        )
        assert http.is_resource_modified(
            env, data=b"not_the_same", ignore_if_range=False
        )

        env["HTTP_IF_RANGE"] = http.http_date(datetime(2008, 1, 1, 13, 30))
        assert http.is_resource_modified(
            env, last_modified=datetime(2008, 1, 1, 14, 00), ignore_if_range=False
        )
        assert not http.is_resource_modified(
            env, last_modified=datetime(2008, 1, 1, 13, 30), ignore_if_range=False
        )
        assert http.is_resource_modified(
            env, last_modified=datetime(2008, 1, 1, 13, 30), ignore_if_range=True
        )

    def test_parse_cookie(self):
        cookies = http.parse_cookie(
            "dismiss-top=6; CP=null*; PHPSESSID=0a539d42abc001cdc762809248d4beed;"
            'a=42; b="\\";"; ; fo234{=bar;blub=Blah; "__Secure-c"=d'
        )
        assert cookies.to_dict() == {
            "CP": "null*",
            "PHPSESSID": "0a539d42abc001cdc762809248d4beed",
            "a": "42",
            "dismiss-top": "6",
            "b": '";',
            "fo234{": "bar",
            "blub": "Blah",
            '"__Secure-c"': "d",
        }

    def test_dump_cookie(self):
        rv = http.dump_cookie(
            "foo", "bar baz blub", 360, httponly=True, sync_expires=False
        )
        assert set(rv.split("; ")) == {
            "HttpOnly",
            "Max-Age=360",
            "Path=/",
            'foo="bar baz blub"',
        }
        assert http.dump_cookie("key", "xxx/") == "key=xxx/; Path=/"
        assert http.dump_cookie("key", "xxx=") == "key=xxx=; Path=/"

    def test_bad_cookies(self):
        cookies = http.parse_cookie(
            "first=IamTheFirst ; a=1; oops ; a=2 ;second = andMeTwo;"
        )
        expect = {
            "first": ["IamTheFirst"],
            "a": ["1", "2"],
            "oops": [""],
            "second": ["andMeTwo"],
        }
        assert cookies.to_dict(flat=False) == expect
        assert cookies["a"] == "1"
        assert cookies.getlist("a") == ["1", "2"]

    def test_empty_keys_are_ignored(self):
        cookies = http.parse_cookie("spam=ham; duck=mallard; ; ")
        expect = {"spam": "ham", "duck": "mallard"}
        assert cookies.to_dict() == expect

    def test_cookie_quoting(self):
        val = http.dump_cookie("foo", "?foo")
        assert val == 'foo="?foo"; Path=/'
        assert http.parse_cookie(val).to_dict() == {"foo": "?foo", "Path": "/"}
        assert http.parse_cookie(r'foo="foo\054bar"').to_dict(), {"foo": "foo,bar"}

    def test_parse_set_cookie_directive(self):
        val = 'foo="?foo"; version="0.1";'
        assert http.parse_cookie(val).to_dict() == {"foo": "?foo", "version": "0.1"}

    def test_cookie_domain_resolving(self):
        val = http.dump_cookie("foo", "bar", domain="\N{SNOWMAN}.com")
        assert val == "foo=bar; Domain=xn--n3h.com; Path=/"

    def test_cookie_unicode_dumping(self):
        val = http.dump_cookie("foo", "\N{SNOWMAN}")
        h = datastructures.Headers()
        h.add("Set-Cookie", val)
        assert h["Set-Cookie"] == 'foo="\\342\\230\\203"; Path=/'

        cookies = http.parse_cookie(h["Set-Cookie"])
        assert cookies["foo"] == "\N{SNOWMAN}"

    def test_cookie_unicode_keys(self):
        # Yes, this is technically against the spec but happens
        val = http.dump_cookie("fö", "fö")
        assert val == _wsgi_encoding_dance('fö="f\\303\\266"; Path=/', "utf-8")
        cookies = http.parse_cookie(val)
        assert cookies["fö"] == "fö"

    def test_cookie_unicode_parsing(self):
        # This is submitted by Firefox if you set a Unicode cookie.
        cookies = http.parse_cookie("fÃ¶=fÃ¶")
        assert cookies["fö"] == "fö"

    def test_cookie_domain_encoding(self):
        val = http.dump_cookie("foo", "bar", domain="\N{SNOWMAN}.com")
        assert val == "foo=bar; Domain=xn--n3h.com; Path=/"

        val = http.dump_cookie("foo", "bar", domain=".\N{SNOWMAN}.com")
        assert val == "foo=bar; Domain=.xn--n3h.com; Path=/"

        val = http.dump_cookie("foo", "bar", domain=".foo.com")
        assert val == "foo=bar; Domain=.foo.com; Path=/"

    def test_cookie_maxsize(self, recwarn):
        val = http.dump_cookie("foo", "bar" * 1360 + "b")
        assert len(recwarn) == 0
        assert len(val) == 4093

        http.dump_cookie("foo", "bar" * 1360 + "ba")
        assert len(recwarn) == 1
        w = recwarn.pop()
        assert "cookie is too large" in str(w.message)

        http.dump_cookie("foo", b"w" * 502, max_size=512)
        assert len(recwarn) == 1
        w = recwarn.pop()
        assert "the limit is 512 bytes" in str(w.message)

    @pytest.mark.parametrize(
        ("samesite", "expected"),
        (
            ("strict", "foo=bar; Path=/; SameSite=Strict"),
            ("lax", "foo=bar; Path=/; SameSite=Lax"),
            ("none", "foo=bar; Path=/; SameSite=None"),
            (None, "foo=bar; Path=/"),
        ),
    )
    def test_cookie_samesite_attribute(self, samesite, expected):
        value = http.dump_cookie("foo", "bar", samesite=samesite)
        assert value == expected

    def test_cookie_samesite_invalid(self):
        with pytest.raises(ValueError):
            http.dump_cookie("foo", "bar", samesite="invalid")


class TestRange:
    def test_if_range_parsing(self):
        rv = http.parse_if_range_header('"Test"')
        assert rv.etag == "Test"
        assert rv.date is None
        assert rv.to_header() == '"Test"'

        # weak information is dropped
        rv = http.parse_if_range_header('W/"Test"')
        assert rv.etag == "Test"
        assert rv.date is None
        assert rv.to_header() == '"Test"'

        # broken etags are supported too
        rv = http.parse_if_range_header("bullshit")
        assert rv.etag == "bullshit"
        assert rv.date is None
        assert rv.to_header() == '"bullshit"'

        rv = http.parse_if_range_header("Thu, 01 Jan 1970 00:00:00 GMT")
        assert rv.etag is None
        assert rv.date == datetime(1970, 1, 1, tzinfo=timezone.utc)
        assert rv.to_header() == "Thu, 01 Jan 1970 00:00:00 GMT"

        for x in "", None:
            rv = http.parse_if_range_header(x)
            assert rv.etag is None
            assert rv.date is None
            assert rv.to_header() == ""

    def test_range_parsing(self):
        rv = http.parse_range_header("bytes=52")
        assert rv is None

        rv = http.parse_range_header("bytes=52-")
        assert rv.units == "bytes"
        assert rv.ranges == [(52, None)]
        assert rv.to_header() == "bytes=52-"

        rv = http.parse_range_header("bytes=52-99")
        assert rv.units == "bytes"
        assert rv.ranges == [(52, 100)]
        assert rv.to_header() == "bytes=52-99"

        rv = http.parse_range_header("bytes=52-99,-1000")
        assert rv.units == "bytes"
        assert rv.ranges == [(52, 100), (-1000, None)]
        assert rv.to_header() == "bytes=52-99,-1000"

        rv = http.parse_range_header("bytes = 1 - 100")
        assert rv.units == "bytes"
        assert rv.ranges == [(1, 101)]
        assert rv.to_header() == "bytes=1-100"

        rv = http.parse_range_header("AWesomes=0-999")
        assert rv.units == "awesomes"
        assert rv.ranges == [(0, 1000)]
        assert rv.to_header() == "awesomes=0-999"

        rv = http.parse_range_header("bytes=-")
        assert rv is None

        rv = http.parse_range_header("bytes=bad")
        assert rv is None

        rv = http.parse_range_header("bytes=bad-1")
        assert rv is None

        rv = http.parse_range_header("bytes=-bad")
        assert rv is None

        rv = http.parse_range_header("bytes=52-99, bad")
        assert rv is None

    def test_content_range_parsing(self):
        rv = http.parse_content_range_header("bytes 0-98/*")
        assert rv.units == "bytes"
        assert rv.start == 0
        assert rv.stop == 99
        assert rv.length is None
        assert rv.to_header() == "bytes 0-98/*"

        rv = http.parse_content_range_header("bytes 0-98/*asdfsa")
        assert rv is None

        rv = http.parse_content_range_header("bytes 0-99/100")
        assert rv.to_header() == "bytes 0-99/100"
        rv.start = None
        rv.stop = None
        assert rv.units == "bytes"
        assert rv.to_header() == "bytes */100"

        rv = http.parse_content_range_header("bytes */100")
        assert rv.start is None
        assert rv.stop is None
        assert rv.length == 100
        assert rv.units == "bytes"


class TestRegression:
    def test_best_match_works(self):
        # was a bug in 0.6
        rv = http.parse_accept_header(
            "foo=,application/xml,application/xhtml+xml,"
            "text/html;q=0.9,text/plain;q=0.8,"
            "image/png,*/*;q=0.5",
            datastructures.MIMEAccept,
        ).best_match(["foo/bar"])
        assert rv == "foo/bar"


@pytest.mark.parametrize(
    "value",
    [
        "Basic V2Vya3pldWc6V2VrcnpldWc=",
        'Digest username=Mufasa, realm="testrealm@host.invalid",'
        ' nonce=dcd98b7102dd2f0e8b11d0f600bfb0c093, uri="/dir/index.html", qop=auth,'
        " nc=00000001, cnonce=0a4f113b, response=6629fae49393a05397450978507c4ef1,"
        " opaque=5ccc069c403ebaf9f0171e9517f40e41",
    ],
)
def test_authorization_to_header(value: str) -> None:
    parsed = http.parse_authorization_header(value)
    assert parsed is not None
    assert parsed.to_header() == value


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        (
            "Sun, 06 Nov 1994 08:49:37 GMT    ",
            datetime(1994, 11, 6, 8, 49, 37, tzinfo=timezone.utc),
        ),
        (
            "Sunday, 06-Nov-94 08:49:37 GMT",
            datetime(1994, 11, 6, 8, 49, 37, tzinfo=timezone.utc),
        ),
        (
            " Sun Nov  6 08:49:37 1994",
            datetime(1994, 11, 6, 8, 49, 37, tzinfo=timezone.utc),
        ),
        ("foo", None),
        (
            " Sun 02 Feb 1343 08:49:37 GMT",
            datetime(1343, 2, 2, 8, 49, 37, tzinfo=timezone.utc),
        ),
        (
            "Thu, 01 Jan 1970 00:00:00 GMT",
            datetime(1970, 1, 1, tzinfo=timezone.utc),
        ),
        ("Thu, 33 Jan 1970 00:00:00 GMT", None),
    ],
)
def test_parse_date(value, expect):
    assert http.parse_date(value) == expect


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        (
            datetime(1994, 11, 6, 8, 49, 37, tzinfo=timezone.utc),
            "Sun, 06 Nov 1994 08:49:37 GMT",
        ),
        (
            datetime(1994, 11, 6, 8, 49, 37, tzinfo=timezone(timedelta(hours=-8))),
            "Sun, 06 Nov 1994 16:49:37 GMT",
        ),
        (datetime(1994, 11, 6, 8, 49, 37), "Sun, 06 Nov 1994 08:49:37 GMT"),
        (0, "Thu, 01 Jan 1970 00:00:00 GMT"),
        (datetime(1970, 1, 1), "Thu, 01 Jan 1970 00:00:00 GMT"),
        (datetime(1, 1, 1), "Mon, 01 Jan 0001 00:00:00 GMT"),
        (datetime(999, 1, 1), "Tue, 01 Jan 0999 00:00:00 GMT"),
        (datetime(1000, 1, 1), "Wed, 01 Jan 1000 00:00:00 GMT"),
        (datetime(2020, 1, 1), "Wed, 01 Jan 2020 00:00:00 GMT"),
        (date(2020, 1, 1), "Wed, 01 Jan 2020 00:00:00 GMT"),
    ],
)
def test_http_date(value, expect):
    assert http.http_date(value) == expect
