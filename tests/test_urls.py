"""
    tests.urls
    ~~~~~~~~~~

    URL helper tests.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import io

import pytest

from . import strict_eq
from werkzeug import urls
from werkzeug.datastructures import OrderedMultiDict


def test_parsing():
    url = urls.url_parse("http://anon:hunter2@[2001:db8:0:1]:80/a/b/c")
    assert url.netloc == "anon:hunter2@[2001:db8:0:1]:80"
    assert url.username == "anon"
    assert url.password == "hunter2"
    assert url.port == 80
    assert url.ascii_host == "2001:db8:0:1"

    assert url.get_file_location() == (None, None)  # no file scheme


@pytest.mark.parametrize("implicit_format", (True, False))
@pytest.mark.parametrize("localhost", ("127.0.0.1", "::1", "localhost"))
def test_fileurl_parsing_windows(implicit_format, localhost, monkeypatch):
    if implicit_format:
        pathformat = None
        monkeypatch.setattr("os.name", "nt")
    else:
        pathformat = "windows"
        monkeypatch.delattr("os.name")  # just to make sure it won't get used

    url = urls.url_parse("file:///C:/Documents and Settings/Foobar/stuff.txt")
    assert url.netloc == ""
    assert url.scheme == "file"
    assert url.get_file_location(pathformat) == (
        None,
        r"C:\Documents and Settings\Foobar\stuff.txt",
    )

    url = urls.url_parse("file://///server.tld/file.txt")
    assert url.get_file_location(pathformat) == ("server.tld", r"file.txt")

    url = urls.url_parse("file://///server.tld")
    assert url.get_file_location(pathformat) == ("server.tld", "")

    url = urls.url_parse("file://///%s" % localhost)
    assert url.get_file_location(pathformat) == (None, "")

    url = urls.url_parse("file://///%s/file.txt" % localhost)
    assert url.get_file_location(pathformat) == (None, r"file.txt")


def test_replace():
    url = urls.url_parse("http://de.wikipedia.org/wiki/Troll")
    strict_eq(
        url.replace(query="foo=bar"),
        urls.url_parse("http://de.wikipedia.org/wiki/Troll?foo=bar"),
    )
    strict_eq(
        url.replace(scheme="https"),
        urls.url_parse("https://de.wikipedia.org/wiki/Troll"),
    )


def test_quoting():
    strict_eq(urls.url_quote("\xf6\xe4\xfc"), "%C3%B6%C3%A4%C3%BC")
    strict_eq(urls.url_unquote(urls.url_quote('#%="\xf6')), '#%="\xf6')
    strict_eq(urls.url_quote_plus("foo bar"), "foo+bar")
    strict_eq(urls.url_unquote_plus("foo+bar"), "foo bar")
    strict_eq(urls.url_quote_plus("foo+bar"), "foo%2Bbar")
    strict_eq(urls.url_unquote_plus("foo%2Bbar"), "foo+bar")
    strict_eq(urls.url_encode({b"a": None, b"b": b"foo bar"}), "b=foo+bar")
    strict_eq(urls.url_encode({"a": None, "b": "foo bar"}), "b=foo+bar")
    strict_eq(
        urls.url_fix("http://de.wikipedia.org/wiki/Elf (Begriffsklärung)"),
        "http://de.wikipedia.org/wiki/Elf%20(Begriffskl%C3%A4rung)",
    )
    strict_eq(urls.url_quote_plus(42), "42")
    strict_eq(urls.url_quote(b"\xff"), "%FF")


def test_bytes_unquoting():
    strict_eq(
        urls.url_unquote(urls.url_quote('#%="\xf6', charset="latin1"), charset=None),
        b'#%="\xf6',
    )


def test_url_decoding():
    x = urls.url_decode(b"foo=42&bar=23&uni=H%C3%A4nsel")
    strict_eq(x["foo"], "42")
    strict_eq(x["bar"], "23")
    strict_eq(x["uni"], "Hänsel")

    x = urls.url_decode(b"foo=42;bar=23;uni=H%C3%A4nsel", separator=b";")
    strict_eq(x["foo"], "42")
    strict_eq(x["bar"], "23")
    strict_eq(x["uni"], "Hänsel")

    x = urls.url_decode(b"%C3%9Ch=H%C3%A4nsel", decode_keys=True)
    strict_eq(x["Üh"], "Hänsel")


def test_url_bytes_decoding():
    x = urls.url_decode(b"foo=42&bar=23&uni=H%C3%A4nsel", charset=None)
    strict_eq(x[b"foo"], b"42")
    strict_eq(x[b"bar"], b"23")
    strict_eq(x[b"uni"], "Hänsel".encode())


def test_streamed_url_decoding():
    item1 = "a" * 100000
    item2 = "b" * 400
    string = (f"a={item1}&b={item2}&c={item2}").encode("ascii")
    gen = urls.url_decode_stream(
        io.BytesIO(string), limit=len(string), return_iterator=True
    )
    strict_eq(next(gen), ("a", item1))
    strict_eq(next(gen), ("b", item2))
    strict_eq(next(gen), ("c", item2))
    pytest.raises(StopIteration, lambda: next(gen))


def test_stream_decoding_string_fails():
    pytest.raises(TypeError, urls.url_decode_stream, "testing")


def test_url_encoding():
    strict_eq(urls.url_encode({"foo": "bar 45"}), "foo=bar+45")
    d = {"foo": 1, "bar": 23, "blah": "Hänsel"}
    strict_eq(urls.url_encode(d, sort=True), "bar=23&blah=H%C3%A4nsel&foo=1")
    strict_eq(
        urls.url_encode(d, sort=True, separator=";"), "bar=23;blah=H%C3%A4nsel;foo=1"
    )


def test_sorted_url_encode():
    strict_eq(
        urls.url_encode(
            {"a": 42, "b": 23, 1: 1, 2: 2}, sort=True, key=lambda i: str(i[0])
        ),
        "1=1&2=2&a=42&b=23",
    )
    strict_eq(
        urls.url_encode(
            {"A": 1, "a": 2, "B": 3, "b": 4},
            sort=True,
            key=lambda x: x[0].lower() + x[0],
        ),
        "A=1&a=2&B=3&b=4",
    )


def test_streamed_url_encoding():
    out = io.StringIO()
    urls.url_encode_stream({"foo": "bar 45"}, out)
    strict_eq(out.getvalue(), "foo=bar+45")

    d = {"foo": 1, "bar": 23, "blah": "Hänsel"}
    out = io.StringIO()
    urls.url_encode_stream(d, out, sort=True)
    strict_eq(out.getvalue(), "bar=23&blah=H%C3%A4nsel&foo=1")
    out = io.StringIO()
    urls.url_encode_stream(d, out, sort=True, separator=";")
    strict_eq(out.getvalue(), "bar=23;blah=H%C3%A4nsel;foo=1")

    gen = urls.url_encode_stream(d, sort=True)
    strict_eq(next(gen), "bar=23")
    strict_eq(next(gen), "blah=H%C3%A4nsel")
    strict_eq(next(gen), "foo=1")
    pytest.raises(StopIteration, lambda: next(gen))


def test_url_fixing():
    x = urls.url_fix("http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)")
    assert x == "http://de.wikipedia.org/wiki/Elf%20(Begriffskl%C3%A4rung)"

    x = urls.url_fix("http://just.a.test/$-_.+!*'(),")
    assert x == "http://just.a.test/$-_.+!*'(),"

    x = urls.url_fix("http://höhöhö.at/höhöhö/hähähä")
    assert x == r"http://xn--hhh-snabb.at/h%C3%B6h%C3%B6h%C3%B6/h%C3%A4h%C3%A4h%C3%A4"


def test_url_fixing_filepaths():
    x = urls.url_fix(r"file://C:\Users\Administrator\My Documents\ÑÈáÇíí")
    assert x == (
        r"file:///C%3A/Users/Administrator/My%20Documents/"
        r"%C3%91%C3%88%C3%A1%C3%87%C3%AD%C3%AD"
    )

    a = urls.url_fix(r"file:/C:/")
    b = urls.url_fix(r"file://C:/")
    c = urls.url_fix(r"file:///C:/")
    assert a == b == c == r"file:///C%3A/"

    x = urls.url_fix(r"file://host/sub/path")
    assert x == r"file://host/sub/path"

    x = urls.url_fix(r"file:///")
    assert x == r"file:///"


def test_url_fixing_qs():
    x = urls.url_fix(b"http://example.com/?foo=%2f%2f")
    assert x == "http://example.com/?foo=%2f%2f"

    x = urls.url_fix(
        "http://acronyms.thefreedictionary.com/"
        "Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation"
    )
    assert x == (
        "http://acronyms.thefreedictionary.com/"
        "Algebraic+Methods+of+Solving+the+Schr%C3%B6dinger+Equation"
    )


def test_iri_support():
    strict_eq(urls.uri_to_iri("http://xn--n3h.net/"), "http://\u2603.net/")
    strict_eq(
        urls.uri_to_iri(b"http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th"),
        "http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th",
    )
    strict_eq(urls.iri_to_uri("http://☃.net/"), "http://xn--n3h.net/")
    strict_eq(
        urls.iri_to_uri("http://üser:pässword@☃.net/påth"),
        "http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th",
    )

    strict_eq(
        urls.uri_to_iri("http://test.com/%3Fmeh?foo=%26%2F"),
        "http://test.com/%3Fmeh?foo=%26%2F",
    )

    # this should work as well, might break on 2.4 because of a broken
    # idna codec
    strict_eq(urls.uri_to_iri(b"/foo"), "/foo")
    strict_eq(urls.iri_to_uri("/foo"), "/foo")

    strict_eq(
        urls.iri_to_uri("http://föö.com:8080/bam/baz"),
        "http://xn--f-1gaa.com:8080/bam/baz",
    )


def test_iri_safe_conversion():
    strict_eq(urls.iri_to_uri("magnet:?foo=bar"), "magnet:?foo=bar")
    strict_eq(urls.iri_to_uri("itms-service://?foo=bar"), "itms-service:?foo=bar")
    strict_eq(
        urls.iri_to_uri("itms-service://?foo=bar", safe_conversion=True),
        "itms-service://?foo=bar",
    )


def test_iri_safe_quoting():
    uri = "http://xn--f-1gaa.com/%2F%25?q=%C3%B6&x=%3D%25#%25"
    iri = "http://föö.com/%2F%25?q=ö&x=%3D%25#%25"
    strict_eq(urls.uri_to_iri(uri), iri)
    strict_eq(urls.iri_to_uri(urls.uri_to_iri(uri)), uri)


def test_ordered_multidict_encoding():
    d = OrderedMultiDict()
    d.add("foo", 1)
    d.add("foo", 2)
    d.add("foo", 3)
    d.add("bar", 0)
    d.add("foo", 4)
    assert urls.url_encode(d) == "foo=1&foo=2&foo=3&bar=0&foo=4"


def test_multidict_encoding():
    d = OrderedMultiDict()
    d.add("2013-10-10T23:26:05.657975+0000", "2013-10-10T23:26:05.657975+0000")
    assert (
        urls.url_encode(d)
        == "2013-10-10T23%3A26%3A05.657975%2B0000=2013-10-10T23%3A26%3A05.657975%2B0000"
    )


def test_href():
    x = urls.Href("http://www.example.com/")
    strict_eq(x("foo"), "http://www.example.com/foo")
    strict_eq(x.foo("bar"), "http://www.example.com/foo/bar")
    strict_eq(x.foo("bar", x=42), "http://www.example.com/foo/bar?x=42")
    strict_eq(x.foo("bar", class_=42), "http://www.example.com/foo/bar?class=42")
    strict_eq(x.foo("bar", {"class": 42}), "http://www.example.com/foo/bar?class=42")
    pytest.raises(AttributeError, lambda: x.__blah__)

    x = urls.Href("blah")
    strict_eq(x.foo("bar"), "blah/foo/bar")

    pytest.raises(TypeError, x.foo, {"foo": 23}, x=42)

    x = urls.Href("")
    strict_eq(x("foo"), "foo")


def test_href_url_join():
    x = urls.Href("test")
    assert x("foo:bar") == "test/foo:bar"
    assert x("http://example.com/") == "test/http://example.com/"
    assert x.a() == "test/a"


def test_href_past_root():
    base_href = urls.Href("http://www.blagga.com/1/2/3")
    strict_eq(base_href("../foo"), "http://www.blagga.com/1/2/foo")
    strict_eq(base_href("../../foo"), "http://www.blagga.com/1/foo")
    strict_eq(base_href("../../../foo"), "http://www.blagga.com/foo")
    strict_eq(base_href("../../../../foo"), "http://www.blagga.com/foo")
    strict_eq(base_href("../../../../../foo"), "http://www.blagga.com/foo")
    strict_eq(base_href("../../../../../../foo"), "http://www.blagga.com/foo")


def test_url_unquote_plus_unicode():
    # was broken in 0.6
    strict_eq(urls.url_unquote_plus("\x6d"), "\x6d")
    assert type(urls.url_unquote_plus("\x6d")) is str


def test_quoting_of_local_urls():
    rv = urls.iri_to_uri("/foo\x8f")
    strict_eq(rv, "/foo%C2%8F")
    assert type(rv) is str


def test_url_attributes():
    rv = urls.url_parse("http://foo%3a:bar%3a@[::1]:80/123?x=y#frag")
    strict_eq(rv.scheme, "http")
    strict_eq(rv.auth, "foo%3a:bar%3a")
    strict_eq(rv.username, "foo:")
    strict_eq(rv.password, "bar:")
    strict_eq(rv.raw_username, "foo%3a")
    strict_eq(rv.raw_password, "bar%3a")
    strict_eq(rv.host, "::1")
    assert rv.port == 80
    strict_eq(rv.path, "/123")
    strict_eq(rv.query, "x=y")
    strict_eq(rv.fragment, "frag")

    rv = urls.url_parse("http://\N{SNOWMAN}.com/")
    strict_eq(rv.host, "\N{SNOWMAN}.com")
    strict_eq(rv.ascii_host, "xn--n3h.com")


def test_url_attributes_bytes():
    rv = urls.url_parse(b"http://foo%3a:bar%3a@[::1]:80/123?x=y#frag")
    strict_eq(rv.scheme, b"http")
    strict_eq(rv.auth, b"foo%3a:bar%3a")
    strict_eq(rv.username, "foo:")
    strict_eq(rv.password, "bar:")
    strict_eq(rv.raw_username, b"foo%3a")
    strict_eq(rv.raw_password, b"bar%3a")
    strict_eq(rv.host, b"::1")
    assert rv.port == 80
    strict_eq(rv.path, b"/123")
    strict_eq(rv.query, b"x=y")
    strict_eq(rv.fragment, b"frag")


def test_url_joining():
    strict_eq(urls.url_join("/foo", "/bar"), "/bar")
    strict_eq(urls.url_join("http://example.com/foo", "/bar"), "http://example.com/bar")
    strict_eq(urls.url_join("file:///tmp/", "test.html"), "file:///tmp/test.html")
    strict_eq(urls.url_join("file:///tmp/x", "test.html"), "file:///tmp/test.html")
    strict_eq(urls.url_join("file:///tmp/x", "../../../x.html"), "file:///x.html")


def test_partial_unencoded_decode():
    ref = "foo=정상처리".encode("euc-kr")
    x = urls.url_decode(ref, charset="euc-kr")
    strict_eq(x["foo"], "정상처리")


def test_iri_to_uri_idempotence_ascii_only():
    uri = "http://www.idempoten.ce"
    uri = urls.iri_to_uri(uri)
    assert urls.iri_to_uri(uri) == uri


def test_iri_to_uri_idempotence_non_ascii():
    uri = "http://\N{SNOWMAN}/\N{SNOWMAN}"
    uri = urls.iri_to_uri(uri)
    assert urls.iri_to_uri(uri) == uri


def test_uri_to_iri_idempotence_ascii_only():
    uri = "http://www.idempoten.ce"
    uri = urls.uri_to_iri(uri)
    assert urls.uri_to_iri(uri) == uri


def test_uri_to_iri_idempotence_non_ascii():
    uri = "http://xn--n3h/%E2%98%83"
    uri = urls.uri_to_iri(uri)
    assert urls.uri_to_iri(uri) == uri


def test_iri_to_uri_to_iri():
    iri = "http://föö.com/"
    uri = urls.iri_to_uri(iri)
    assert urls.uri_to_iri(uri) == iri


def test_uri_to_iri_to_uri():
    uri = "http://xn--f-rgao.com/%C3%9E"
    iri = urls.uri_to_iri(uri)
    assert urls.iri_to_uri(iri) == uri


def test_uri_iri_normalization():
    uri = "http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93"
    iri = "http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713"

    tests = [
        "http://föñ.com/\N{BALLOT BOX}/fred?utf8=\u2713",
        "http://xn--f-rgao.com/\u2610/fred?utf8=\N{CHECK MARK}",
        b"http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93",
        "http://xn--f-rgao.com/%E2%98%90/fred?utf8=%E2%9C%93",
        "http://föñ.com/\u2610/fred?utf8=%E2%9C%93",
        b"http://xn--f-rgao.com/\xe2\x98\x90/fred?utf8=\xe2\x9c\x93",
    ]

    for test in tests:
        assert urls.uri_to_iri(test) == iri
        assert urls.iri_to_uri(test) == uri
        assert urls.uri_to_iri(urls.iri_to_uri(test)) == iri
        assert urls.iri_to_uri(urls.uri_to_iri(test)) == uri
        assert urls.uri_to_iri(urls.uri_to_iri(test)) == iri
        assert urls.iri_to_uri(urls.iri_to_uri(test)) == uri


def test_uri_to_iri_dont_unquote_space():
    assert urls.uri_to_iri("abc%20def") == "abc%20def"


def test_iri_to_uri_dont_quote_reserved():
    assert urls.iri_to_uri("/path[bracket]?(paren)") == "/path[bracket]?(paren)"
