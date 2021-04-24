import contextlib
import json
import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO

import pytest

from werkzeug import Response
from werkzeug import wrappers
from werkzeug.datastructures import Accept
from werkzeug.datastructures import CharsetAccept
from werkzeug.datastructures import CombinedMultiDict
from werkzeug.datastructures import Headers
from werkzeug.datastructures import ImmutableList
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.datastructures import ImmutableOrderedMultiDict
from werkzeug.datastructures import LanguageAccept
from werkzeug.datastructures import MIMEAccept
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import RequestedRangeNotSatisfiable
from werkzeug.exceptions import SecurityError
from werkzeug.http import COEP
from werkzeug.http import COOP
from werkzeug.http import generate_etag
from werkzeug.test import Client
from werkzeug.test import create_environ
from werkzeug.test import run_wsgi_app
from werkzeug.wrappers.cors import CORSRequestMixin
from werkzeug.wrappers.cors import CORSResponseMixin
from werkzeug.wrappers.json import JSONMixin
from werkzeug.wsgi import LimitedStream
from werkzeug.wsgi import wrap_file


@wrappers.Request.application
def request_demo_app(request):
    assert "werkzeug.request" in request.environ
    return Response()


def assert_environ(environ, method):
    assert environ["REQUEST_METHOD"] == method
    assert environ["PATH_INFO"] == "/"
    assert environ["SCRIPT_NAME"] == ""
    assert environ["SERVER_NAME"] == "localhost"
    assert environ["wsgi.version"] == (1, 0)
    assert environ["wsgi.url_scheme"] == "http"


def test_base_request():
    client = Client(request_demo_app)

    # get requests
    response = client.get("/?foo=bar&foo=hehe")
    request = response.request
    assert request.args == MultiDict([("foo", "bar"), ("foo", "hehe")])
    assert request.form == MultiDict()
    assert request.data == b""
    assert_environ(request.environ, "GET")

    # post requests with form data
    response = client.post(
        "/?blub=blah",
        data="foo=blub+hehe&blah=42",
        content_type="application/x-www-form-urlencoded",
    )
    request = response.request
    assert request.args == MultiDict([("blub", "blah")])
    assert request.form == MultiDict([("foo", "blub hehe"), ("blah", "42")])
    assert request.data == b""
    # currently we do not guarantee that the values are ordered correctly
    # for post data.
    # assert response['form_as_list'] == [('foo', ['blub hehe']), ('blah', ['42'])]
    assert_environ(request.environ, "POST")

    # patch requests with form data
    response = client.patch(
        "/?blub=blah",
        data="foo=blub+hehe&blah=42",
        content_type="application/x-www-form-urlencoded",
    )
    request = response.request
    assert request.args == MultiDict([("blub", "blah")])
    assert request.form == MultiDict([("foo", "blub hehe"), ("blah", "42")])
    assert request.data == b""
    assert_environ(request.environ, "PATCH")

    # post requests with json data
    json = b'{"foo": "bar", "blub": "blah"}'
    response = client.post("/?a=b", data=json, content_type="application/json")
    request = response.request
    assert request.data == json
    assert request.args == MultiDict([("a", "b")])
    assert request.form == MultiDict()


def test_query_string_is_bytes():
    req = wrappers.Request.from_values("/?foo=%2f")
    assert req.query_string == b"foo=%2f"


def test_request_repr():
    req = wrappers.Request.from_values("/foobar")
    assert "<Request 'http://localhost/foobar' [GET]>" == repr(req)
    req = wrappers.Request.from_values("/привет")
    assert "<Request 'http://localhost/привет' [GET]>" == repr(req)


def test_access_route():
    req = wrappers.Request.from_values(
        headers={"X-Forwarded-For": "192.168.1.2, 192.168.1.1"},
        environ_base={"REMOTE_ADDR": "192.168.1.3"},
    )
    assert req.access_route == ["192.168.1.2", "192.168.1.1"]
    assert req.remote_addr == "192.168.1.3"

    req = wrappers.Request.from_values(environ_base={"REMOTE_ADDR": "192.168.1.3"})
    assert list(req.access_route) == ["192.168.1.3"]


def test_url_request_descriptors():
    req = wrappers.Request.from_values("/bar?foo=baz", "http://example.com/test")
    assert req.path == "/bar"
    assert req.full_path == "/bar?foo=baz"
    assert req.script_root == "/test"
    assert req.url == "http://example.com/test/bar?foo=baz"
    assert req.base_url == "http://example.com/test/bar"
    assert req.url_root == "http://example.com/test/"
    assert req.host_url == "http://example.com/"
    assert req.host == "example.com"
    assert req.scheme == "http"

    req = wrappers.Request.from_values("/bar?foo=baz", "https://example.com/test")
    assert req.scheme == "https"


def test_url_request_descriptors_query_quoting():
    next = "http%3A%2F%2Fwww.example.com%2F%3Fnext%3D%2Fbaz%23my%3Dhash"
    req = wrappers.Request.from_values(f"/bar?next={next}", "http://example.com/")
    assert req.path == "/bar"
    assert req.full_path == f"/bar?next={next}"
    assert req.url == f"http://example.com/bar?next={next}"


def test_url_request_descriptors_hosts():
    req = wrappers.Request.from_values("/bar?foo=baz", "http://example.com/test")
    req.trusted_hosts = ["example.com"]
    assert req.path == "/bar"
    assert req.full_path == "/bar?foo=baz"
    assert req.script_root == "/test"
    assert req.url == "http://example.com/test/bar?foo=baz"
    assert req.base_url == "http://example.com/test/bar"
    assert req.url_root == "http://example.com/test/"
    assert req.host_url == "http://example.com/"
    assert req.host == "example.com"
    assert req.scheme == "http"

    req = wrappers.Request.from_values("/bar?foo=baz", "https://example.com/test")
    assert req.scheme == "https"

    req = wrappers.Request.from_values("/bar?foo=baz", "http://example.com/test")
    req.trusted_hosts = ["example.org"]
    pytest.raises(SecurityError, lambda: req.url)
    pytest.raises(SecurityError, lambda: req.base_url)
    pytest.raises(SecurityError, lambda: req.url_root)
    pytest.raises(SecurityError, lambda: req.host_url)
    pytest.raises(SecurityError, lambda: req.host)


def test_authorization():
    request = wrappers.Request.from_values(
        headers={"Authorization": "Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="}
    )
    a = request.authorization
    assert a.type == "basic"
    assert a.username == "Aladdin"
    assert a.password == "open sesame"


def test_authorization_with_unicode():
    request = wrappers.Request.from_values(
        headers={"Authorization": "Basic 0YDRg9GB0YHQutC40IE60JHRg9C60LLRiw=="}
    )
    a = request.authorization
    assert a.type == "basic"
    assert a.username == "русскиЁ"
    assert a.password == "Буквы"


def test_request_application():
    @wrappers.Request.application
    def application(request):
        return wrappers.Response("Hello World!")

    @wrappers.Request.application
    def failing_application(request):
        raise BadRequest()

    resp = wrappers.Response.from_app(application, create_environ())
    assert resp.data == b"Hello World!"
    assert resp.status_code == 200

    resp = wrappers.Response.from_app(failing_application, create_environ())
    assert b"Bad Request" in resp.data
    assert resp.status_code == 400


def test_request_access_control():
    request = wrappers.Request.from_values(
        headers={
            "Origin": "https://palletsprojects.com",
            "Access-Control-Request-Headers": "X-A, X-B",
            "Access-Control-Request-Method": "PUT",
        }
    )
    assert request.origin == "https://palletsprojects.com"
    assert request.access_control_request_headers == {"X-A", "X-B"}
    assert request.access_control_request_method == "PUT"


def test_response_access_control():
    response = wrappers.Response("Hello World")
    assert response.access_control_allow_credentials is False
    response.access_control_allow_credentials = True
    response.access_control_allow_headers = ["X-A", "X-B"]
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert set(response.headers["Access-Control-Allow-Headers"].split(", ")) == {
        "X-A",
        "X-B",
    }


def test_base_response():
    response = wrappers.Response("öäü")
    assert response.get_data() == "öäü".encode()

    # writing
    response = wrappers.Response("foo")
    response.stream.write("bar")
    assert response.get_data() == b"foobar"

    # set cookie
    response = wrappers.Response()
    response.set_cookie(
        "foo",
        value="bar",
        max_age=60,
        expires=0,
        path="/blub",
        domain="example.org",
        samesite="Strict",
    )
    assert response.headers.to_wsgi_list() == [
        ("Content-Type", "text/plain; charset=utf-8"),
        (
            "Set-Cookie",
            "foo=bar; Domain=example.org;"
            " Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=60;"
            " Path=/blub; SameSite=Strict",
        ),
    ]

    # delete cookie
    response = wrappers.Response()
    response.delete_cookie("foo")
    assert response.headers.to_wsgi_list() == [
        ("Content-Type", "text/plain; charset=utf-8"),
        (
            "Set-Cookie",
            "foo=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/",
        ),
    ]

    # close call forwarding
    closed = []

    class Iterable:
        def __next__(self):
            raise StopIteration()

        def __iter__(self):
            return self

        def close(self):
            closed.append(True)

    response = wrappers.Response(Iterable())
    response.call_on_close(lambda: closed.append(True))
    app_iter, status, headers = run_wsgi_app(response, create_environ(), buffered=True)
    assert status == "200 OK"
    assert "".join(app_iter) == ""
    assert len(closed) == 2

    # with statement
    del closed[:]
    response = wrappers.Response(Iterable())
    with response:
        pass
    assert len(closed) == 1


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (200, "200 OK"),
        (404, "404 NOT FOUND"),
        (588, "588 UNKNOWN"),
        (999, "999 UNKNOWN"),
    ],
)
def test_response_set_status_code(status_code, expected_status):
    response = wrappers.Response()
    response.status_code = status_code
    assert response.status_code == status_code
    assert response.status == expected_status


@pytest.mark.parametrize(
    ("status", "expected_status_code", "expected_status"),
    [
        ("404", 404, "404 NOT FOUND"),
        ("588", 588, "588 UNKNOWN"),
        ("999", 999, "999 UNKNOWN"),
        ("200 OK", 200, "200 OK"),
        ("999 WTF", 999, "999 WTF"),
        ("wtf", 0, "0 wtf"),
        ("200 TEA POT", 200, "200 TEA POT"),
        (200, 200, "200 OK"),
        (400, 400, "400 BAD REQUEST"),
    ],
)
def test_response_set_status(status, expected_status_code, expected_status):
    response = wrappers.Response()
    response.status = status
    assert response.status_code == expected_status_code
    assert response.status == expected_status

    response = wrappers.Response(status=status)
    assert response.status_code == expected_status_code
    assert response.status == expected_status


def test_response_init_status_empty_string():
    # invalid status codes
    with pytest.raises(ValueError) as info:
        wrappers.Response(None, "")

    assert "Empty status argument" in str(info.value)


def test_response_init_status_tuple():
    with pytest.raises(TypeError) as info:
        wrappers.Response(None, tuple())

    assert "Invalid status argument" in str(info.value)


def test_type_forcing():
    def wsgi_application(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/html")])
        return ["Hello World!"]

    base_response = wrappers.Response("Hello World!", content_type="text/html")

    class SpecialResponse(wrappers.Response):
        def foo(self):
            return 42

    # good enough for this simple application, but don't ever use that in
    # real world examples!
    fake_env = {}

    for orig_resp in wsgi_application, base_response:
        response = SpecialResponse.force_type(orig_resp, fake_env)
        assert response.__class__ is SpecialResponse
        assert response.foo() == 42
        assert response.get_data() == b"Hello World!"
        assert response.content_type == "text/html"

    # without env, no arbitrary conversion
    pytest.raises(TypeError, SpecialResponse.force_type, wsgi_application)


def test_accept():
    request = wrappers.Request(
        {
            "HTTP_ACCEPT": "text/xml,application/xml,application/xhtml+xml,"
            "text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5",
            "HTTP_ACCEPT_CHARSET": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "HTTP_ACCEPT_ENCODING": "gzip,deflate",
            "HTTP_ACCEPT_LANGUAGE": "en-us,en;q=0.5",
            "SERVER_NAME": "eggs",
            "SERVER_PORT": "80",
        }
    )
    assert request.accept_mimetypes == MIMEAccept(
        [
            ("text/xml", 1),
            ("application/xml", 1),
            ("application/xhtml+xml", 1),
            ("image/png", 1),
            ("text/html", 0.9),
            ("text/plain", 0.8),
            ("*/*", 0.5),
        ]
    )
    assert request.accept_charsets == CharsetAccept(
        [("ISO-8859-1", 1), ("utf-8", 0.7), ("*", 0.7)]
    )
    assert request.accept_encodings == Accept([("gzip", 1), ("deflate", 1)])
    assert request.accept_languages == LanguageAccept([("en-us", 1), ("en", 0.5)])

    request = wrappers.Request(
        {"HTTP_ACCEPT": "", "SERVER_NAME": "example.org", "SERVER_PORT": "80"}
    )
    assert request.accept_mimetypes == MIMEAccept()


def test_etag_request():
    request = wrappers.Request(
        {
            "HTTP_CACHE_CONTROL": "no-store, no-cache",
            "HTTP_IF_MATCH": 'W/"foo", bar, "baz"',
            "HTTP_IF_NONE_MATCH": 'W/"foo", bar, "baz"',
            "HTTP_IF_MODIFIED_SINCE": "Tue, 22 Jan 2008 11:18:44 GMT",
            "HTTP_IF_UNMODIFIED_SINCE": "Tue, 22 Jan 2008 11:18:44 GMT",
            "SERVER_NAME": "eggs",
            "SERVER_PORT": "80",
        }
    )
    assert request.cache_control.no_store
    assert request.cache_control.no_cache

    for etags in request.if_match, request.if_none_match:
        assert etags("bar")
        assert etags.contains_raw('W/"foo"')
        assert etags.contains_weak("foo")
        assert not etags.contains("foo")

    dt = datetime(2008, 1, 22, 11, 18, 44, tzinfo=timezone.utc)
    assert request.if_modified_since == dt
    assert request.if_unmodified_since == dt


@pytest.mark.parametrize(
    ("user_agent", "browser", "platform", "version", "language"),
    (
        (
            "Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US; rv:1.8.1.11) "
            "Gecko/20071127 Firefox/2.0.0.11",
            "firefox",
            "macos",
            "2.0.0.11",
            "en-US",
        ),
        (
            "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; de-DE) Opera 8.54",
            "opera",
            "windows",
            "8.54",
            "de-DE",
        ),
        (
            "Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420 "
            "(KHTML, like Gecko) Version/3.0 Mobile/1A543a Safari/419.3",
            "safari",
            "iphone",
            "3.0",
            "en",
        ),
        (
            "Bot Googlebot/2.1 ( http://www.googlebot.com/bot.html)",
            "google",
            None,
            "2.1",
            None,
        ),
        (
            "Mozilla/5.0 (X11; CrOS armv7l 3701.81.0) AppleWebKit/537.31 "
            "(KHTML, like Gecko) Chrome/26.0.1410.57 Safari/537.31",
            "chrome",
            "chromeos",
            "26.0.1410.57",
            None,
        ),
        (
            "Mozilla/5.0 (Windows NT 6.3; Trident/7.0; .NET4.0E; rv:11.0) like Gecko",
            "msie",
            "windows",
            "11.0",
            None,
        ),
        (
            "Mozilla/5.0 (SymbianOS/9.3; Series60/3.2 NokiaE5-00/101.003; "
            "Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/533.4 "
            "(KHTML, like Gecko) NokiaBrowser/7.3.1.35 Mobile Safari/533.4 3gpp-gba",
            "safari",
            "symbian",
            "533.4",
            None,
        ),
        (
            "Mozilla/5.0 (X11; OpenBSD amd64; rv:45.0) Gecko/20100101 Firefox/45.0",
            "firefox",
            "openbsd",
            "45.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; NetBSD amd64; rv:45.0) Gecko/20100101 Firefox/45.0",
            "firefox",
            "netbsd",
            "45.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; FreeBSD amd64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/48.0.2564.103 Safari/537.36",
            "chrome",
            "freebsd",
            "48.0.2564.103",
            None,
        ),
        (
            "Mozilla/5.0 (X11; FreeBSD amd64; rv:45.0) Gecko/20100101 Firefox/45.0",
            "firefox",
            "freebsd",
            "45.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; U; NetBSD amd64; en-US; rv:) Gecko/20150921 "
            "SeaMonkey/1.1.18",
            "seamonkey",
            "netbsd",
            "1.1.18",
            "en-US",
        ),
        (
            "Mozilla/5.0 (Windows; U; Windows NT 6.2; WOW64; rv:1.8.0.7) "
            "Gecko/20110321 MultiZilla/4.33.2.6a SeaMonkey/8.6.55",
            "seamonkey",
            "windows",
            "8.6.55",
            None,
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:12.0) Gecko/20120427 Firefox/12.0 "
            "SeaMonkey/2.9",
            "seamonkey",
            "linux",
            "2.9",
            None,
        ),
        (
            "Mozilla/5.0 (compatible; Baiduspider/2.0; "
            "+http://www.baidu.com/search/spider.html)",
            "baidu",
            None,
            "2.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; SunOS i86pc; rv:38.0) Gecko/20100101 Firefox/38.0",
            "firefox",
            "solaris",
            "38.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0 "
            "Iceweasel/38.7.1",
            "firefox",
            "linux",
            "38.0",
            None,
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
            "chrome",
            "windows",
            "50.0.2661.75",
            None,
        ),
        (
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "bing",
            None,
            "2.0",
            None,
        ),
        (
            "Mozilla/5.0 (X11; DragonFly x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36",
            "chrome",
            "dragonflybsd",
            "47.0.2526.106",
            None,
        ),
        (
            "Mozilla/5.0 (X11; U; DragonFly i386; de; rv:1.9.1) "
            "Gecko/20090720 Firefox/3.5.1",
            "firefox",
            "dragonflybsd",
            "3.5.1",
            "de",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36"
            "(KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36 OPR/60.0.3255.95",
            "opera",
            "macos",
            "60.0.3255.95",
            None,
        ),
        (
            "Mozilla/5.0 (Linux; Android 4.4.4; Google Nexus 7 2013 - 4.4.4 - "
            "API 19 - 1200x1920 Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/51.0.2704.106 Crosswalk/21.51.546.7 Safari/537.36",
            "chrome",
            "android",
            "51.0.2704.106",
            None,
        ),
        (
            "Mozilla/5.0 (Linux; Android; motorola edge) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/85.0.4183.81 Mobile Safari/537.36",
            "chrome",
            "android",
            "85.0.4183.81",
            None,
        ),
        (
            "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; Trident/4.0; "
            ".NET CLR 1.1.4322)",
            "msie",
            "windows",
            "7.0",
            None,
        ),
    ),
)
def test_user_agent(user_agent, browser, platform, version, language):
    request = wrappers.Request({"HTTP_USER_AGENT": user_agent})

    assert request.user_agent.to_header() == user_agent
    assert str(request.user_agent) == user_agent
    assert request.user_agent.string == user_agent

    with pytest.deprecated_call():
        assert request.user_agent.browser == browser

    with pytest.deprecated_call():
        assert request.user_agent.platform == platform

    with pytest.deprecated_call():
        assert request.user_agent.version == version

    with pytest.deprecated_call():
        assert request.user_agent.language == language

    with pytest.deprecated_call():
        assert bool(request.user_agent)

    from werkzeug import useragents

    with pytest.deprecated_call():
        useragents.UserAgent("")

    with pytest.deprecated_call(match="environ"):
        useragents.UserAgent({})

    with pytest.deprecated_call():
        useragents.UserAgentParser()


def test_invalid_user_agent():
    request = wrappers.Request(
        {"HTTP_USER_AGENT": "foo", "SERVER_NAME": "eggs", "SERVER_PORT": "80"}
    )

    with pytest.deprecated_call():
        assert not request.user_agent


def test_stream_wrapping():
    class LowercasingStream:
        def __init__(self, stream):
            self._stream = stream

        def read(self, size=-1):
            return self._stream.read(size).lower()

        def readline(self, size=-1):
            return self._stream.readline(size).lower()

    data = b"foo=Hello+World"
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )
    req.stream = LowercasingStream(req.stream)
    assert req.form["foo"] == "hello world"


def test_data_descriptor_triggers_parsing():
    data = b"foo=Hello+World"
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )

    assert req.data == b""
    assert req.form["foo"] == "Hello World"


def test_get_data_method_parsing_caching_behavior():
    data = b"foo=Hello+World"
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )

    # get_data() caches, so form stays available
    assert req.get_data() == data
    assert req.form["foo"] == "Hello World"
    assert req.get_data() == data

    # here we access the form data first, caching is bypassed
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )
    assert req.form["foo"] == "Hello World"
    assert req.get_data() == b""

    # Another case is uncached get data which trashes everything
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )
    assert req.get_data(cache=False) == data
    assert req.get_data(cache=False) == b""
    assert req.form == {}

    # Or we can implicitly start the form parser which is similar to
    # the old .data behavior
    req = wrappers.Request.from_values(
        "/", method="POST", data=data, content_type="application/x-www-form-urlencoded"
    )
    assert req.get_data(parse_form_data=True) == b""
    assert req.form["foo"] == "Hello World"


def test_etag_response():
    response = wrappers.Response("Hello World")
    assert response.get_etag() == (None, None)
    response.add_etag()
    assert response.get_etag() == ("0a4d55a8d778e5022fab701977c5d840bbc486d0", False)
    assert not response.cache_control
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 60
    response.headers["Content-Length"] = len(response.get_data())
    assert response.headers["Cache-Control"] in (
        "must-revalidate, max-age=60",
        "max-age=60, must-revalidate",
    )

    assert "date" not in response.headers
    env = create_environ()
    env.update({"REQUEST_METHOD": "GET", "HTTP_IF_NONE_MATCH": response.get_etag()[0]})
    response.make_conditional(env)
    assert "date" in response.headers

    # after the thing is invoked by the server as wsgi application
    # (we're emulating this here), there must not be any entity
    # headers left and the status code would have to be 304
    resp = wrappers.Response.from_app(response, env)
    assert resp.status_code == 304
    assert "content-length" not in resp.headers

    # make sure date is not overriden
    response = wrappers.Response("Hello World")
    response.date = 1337
    d = response.date
    response.make_conditional(env)
    assert response.date == d

    # make sure content length is only set if missing
    response = wrappers.Response("Hello World")
    response.content_length = 999
    response.make_conditional(env)
    assert response.content_length == 999


def test_etag_response_412():
    response = wrappers.Response("Hello World")
    assert response.get_etag() == (None, None)
    response.add_etag()
    assert response.get_etag() == ("0a4d55a8d778e5022fab701977c5d840bbc486d0", False)
    assert not response.cache_control
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 60
    response.headers["Content-Length"] = len(response.get_data())
    assert response.headers["Cache-Control"] in (
        "must-revalidate, max-age=60",
        "max-age=60, must-revalidate",
    )

    assert "date" not in response.headers
    env = create_environ()
    env.update(
        {"REQUEST_METHOD": "GET", "HTTP_IF_MATCH": f"{response.get_etag()[0]}xyz"}
    )
    response.make_conditional(env)
    assert "date" in response.headers

    # after the thing is invoked by the server as wsgi application
    # (we're emulating this here), there must not be any entity
    # headers left and the status code would have to be 412
    resp = wrappers.Response.from_app(response, env)
    assert resp.status_code == 412
    # Make sure there is a body still
    assert resp.data != b""

    # make sure date is not overriden
    response = wrappers.Response("Hello World")
    response.date = 1337
    d = response.date
    response.make_conditional(env)
    assert response.date == d

    # make sure content length is only set if missing
    response = wrappers.Response("Hello World")
    response.content_length = 999
    response.make_conditional(env)
    assert response.content_length == 999


def test_range_request_basic():
    env = create_environ()
    response = wrappers.Response("Hello World")
    env["HTTP_RANGE"] = "bytes=0-4"
    response.make_conditional(env, accept_ranges=True, complete_length=11)
    assert response.status_code == 206
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Range"] == "bytes 0-4/11"
    assert response.headers["Content-Length"] == "5"
    assert response.data == b"Hello"


def test_range_request_out_of_bound():
    env = create_environ()
    response = wrappers.Response("Hello World")
    env["HTTP_RANGE"] = "bytes=6-666"
    response.make_conditional(env, accept_ranges=True, complete_length=11)
    assert response.status_code == 206
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Range"] == "bytes 6-10/11"
    assert response.headers["Content-Length"] == "5"
    assert response.data == b"World"


def test_range_request_with_file():
    env = create_environ()
    resources = os.path.join(os.path.dirname(__file__), "res")
    fname = os.path.join(resources, "test.txt")
    with open(fname, "rb") as f:
        fcontent = f.read()
    with open(fname, "rb") as f:
        response = wrappers.Response(wrap_file(env, f))
        env["HTTP_RANGE"] = "bytes=0-0"
        response.make_conditional(
            env, accept_ranges=True, complete_length=len(fcontent)
        )
        assert response.status_code == 206
        assert response.headers["Accept-Ranges"] == "bytes"
        assert response.headers["Content-Range"] == f"bytes 0-0/{len(fcontent)}"
        assert response.headers["Content-Length"] == "1"
        assert response.data == fcontent[:1]


def test_range_request_with_complete_file():
    env = create_environ()
    resources = os.path.join(os.path.dirname(__file__), "res")
    fname = os.path.join(resources, "test.txt")
    with open(fname, "rb") as f:
        fcontent = f.read()
    with open(fname, "rb") as f:
        fsize = os.path.getsize(fname)
        response = wrappers.Response(wrap_file(env, f))
        env["HTTP_RANGE"] = f"bytes=0-{fsize - 1}"
        response.make_conditional(env, accept_ranges=True, complete_length=fsize)
        assert response.status_code == 206
        assert response.headers["Accept-Ranges"] == "bytes"
        assert response.headers["Content-Range"] == f"bytes 0-{fsize - 1}/{fsize}"
        assert response.headers["Content-Length"] == str(fsize)
        assert response.data == fcontent


@pytest.mark.parametrize("value", [None, 0])
def test_range_request_without_complete_length(value):
    env = create_environ(headers={"Range": "bytes=0-10"})
    response = wrappers.Response("Hello World")
    response.make_conditional(env, accept_ranges=True, complete_length=value)
    assert response.status_code == 200
    assert response.data == b"Hello World"


def test_invalid_range_request():
    env = create_environ()
    response = wrappers.Response("Hello World")
    env["HTTP_RANGE"] = "bytes=-"
    with pytest.raises(RequestedRangeNotSatisfiable):
        response.make_conditional(env, accept_ranges=True, complete_length=11)


def test_etag_response_freezing():
    response = Response("Hello World")
    response.freeze()
    assert response.get_etag() == (str(generate_etag(b"Hello World")), False)


def test_authenticate():
    resp = wrappers.Response()
    resp.www_authenticate.type = "basic"
    resp.www_authenticate.realm = "Testing"
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Testing"'
    resp.www_authenticate.realm = None
    resp.www_authenticate.type = None
    assert "WWW-Authenticate" not in resp.headers


def test_authenticate_quoted_qop():
    # Example taken from https://github.com/pallets/werkzeug/issues/633
    resp = wrappers.Response()
    resp.www_authenticate.set_digest("REALM", "NONCE", qop=("auth", "auth-int"))

    actual = set(f"{resp.headers['WWW-Authenticate']},".split())
    expected = set('Digest nonce="NONCE", realm="REALM", qop="auth, auth-int",'.split())
    assert actual == expected

    resp.www_authenticate.set_digest("REALM", "NONCE", qop=("auth",))

    actual = set(f"{resp.headers['WWW-Authenticate']},".split())
    expected = set('Digest nonce="NONCE", realm="REALM", qop="auth",'.split())
    assert actual == expected


def test_response_stream():
    response = wrappers.Response()
    response.stream.write("Hello ")
    response.stream.write("World!")
    assert response.response == ["Hello ", "World!"]
    assert response.get_data() == b"Hello World!"


def test_common_response_descriptors():
    response = wrappers.Response()
    response.mimetype = "text/html"
    assert response.mimetype == "text/html"
    assert response.content_type == "text/html; charset=utf-8"
    assert response.mimetype_params == {"charset": "utf-8"}
    response.mimetype_params["x-foo"] = "yep"
    del response.mimetype_params["charset"]
    assert response.content_type == "text/html; x-foo=yep"

    now = datetime.now(timezone.utc).replace(microsecond=0)

    assert response.content_length is None
    response.content_length = "42"
    assert response.content_length == 42

    for attr in "date", "expires":
        assert getattr(response, attr) is None
        setattr(response, attr, now)
        assert getattr(response, attr) == now

    assert response.age is None
    age_td = timedelta(days=1, minutes=3, seconds=5)
    response.age = age_td
    assert response.age == age_td
    response.age = 42
    assert response.age == timedelta(seconds=42)

    assert response.retry_after is None
    response.retry_after = now
    assert response.retry_after == now

    assert not response.vary
    response.vary.add("Cookie")
    response.vary.add("Content-Language")
    assert "cookie" in response.vary
    assert response.vary.to_header() == "Cookie, Content-Language"
    response.headers["Vary"] = "Content-Encoding"
    assert response.vary.as_set() == {"content-encoding"}

    response.allow.update(["GET", "POST"])
    assert response.headers["Allow"] == "GET, POST"

    response.content_language.add("en-US")
    response.content_language.add("fr")
    assert response.headers["Content-Language"] == "en-US, fr"


def test_common_request_descriptors():
    request = wrappers.Request.from_values(
        content_type="text/html; charset=utf-8",
        content_length="23",
        headers={
            "Referer": "http://www.example.com/",
            "Date": "Sat, 28 Feb 2009 19:04:35 GMT",
            "Max-Forwards": "10",
            "Pragma": "no-cache",
            "Content-Encoding": "gzip",
            "Content-MD5": "9a3bc6dbc47a70db25b84c6e5867a072",
        },
    )

    assert request.content_type == "text/html; charset=utf-8"
    assert request.mimetype == "text/html"
    assert request.mimetype_params == {"charset": "utf-8"}
    assert request.content_length == 23
    assert request.referrer == "http://www.example.com/"
    assert request.date == datetime(2009, 2, 28, 19, 4, 35, tzinfo=timezone.utc)
    assert request.max_forwards == 10
    assert "no-cache" in request.pragma
    assert request.content_encoding == "gzip"
    assert request.content_md5 == "9a3bc6dbc47a70db25b84c6e5867a072"


def test_request_mimetype_always_lowercase():
    request = wrappers.Request.from_values(content_type="APPLICATION/JSON")
    assert request.mimetype == "application/json"


def test_shallow_mode():
    request = wrappers.Request(
        {"QUERY_STRING": "foo=bar", "SERVER_NAME": "eggs", "SERVER_PORT": "80"},
        shallow=True,
    )
    assert request.args["foo"] == "bar"
    pytest.raises(RuntimeError, lambda: request.stream)
    pytest.raises(RuntimeError, lambda: request.data)
    pytest.raises(RuntimeError, lambda: request.form)


def test_form_parsing_failed():
    data = b"--blah\r\n"
    request = wrappers.Request.from_values(
        input_stream=BytesIO(data),
        content_length=len(data),
        content_type="multipart/form-data; boundary=foo",
        method="POST",
    )
    assert not request.files
    assert not request.form

    # Bad Content-Type
    data = b"test"
    request = wrappers.Request.from_values(
        input_stream=BytesIO(data),
        content_length=len(data),
        content_type=", ",
        method="POST",
    )
    assert not request.form


def test_file_closing():
    data = (
        b"--foo\r\n"
        b'Content-Disposition: form-data; name="foo"; filename="foo.txt"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"file contents, just the contents\r\n"
        b"--foo--"
    )
    req = wrappers.Request.from_values(
        input_stream=BytesIO(data),
        content_length=len(data),
        content_type="multipart/form-data; boundary=foo",
        method="POST",
    )
    foo = req.files["foo"]
    assert foo.mimetype == "text/plain"
    assert foo.filename == "foo.txt"

    assert foo.closed is False
    req.close()
    assert foo.closed is True


def test_file_closing_with():
    data = (
        b"--foo\r\n"
        b'Content-Disposition: form-data; name="foo"; filename="foo.txt"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"file contents, just the contents\r\n"
        b"--foo--"
    )
    req = wrappers.Request.from_values(
        input_stream=BytesIO(data),
        content_length=len(data),
        content_type="multipart/form-data; boundary=foo",
        method="POST",
    )
    with req:
        foo = req.files["foo"]
        assert foo.mimetype == "text/plain"
        assert foo.filename == "foo.txt"

    assert foo.closed is True


def test_url_charset_reflection():
    req = wrappers.Request.from_values()
    req.charset = "utf-7"
    assert req.url_charset == "utf-7"


def test_response_streamed():
    r = wrappers.Response()
    assert not r.is_streamed
    r = wrappers.Response("Hello World")
    assert not r.is_streamed
    r = wrappers.Response(["foo", "bar"])
    assert not r.is_streamed

    def gen():
        if 0:
            yield None

    r = wrappers.Response(gen())
    assert r.is_streamed


def test_response_iter_wrapping():
    def uppercasing(iterator):
        for item in iterator:
            yield item.upper()

    def generator():
        yield "foo"
        yield "bar"

    req = wrappers.Request.from_values()
    resp = wrappers.Response(generator())
    del resp.headers["Content-Length"]
    resp.response = uppercasing(resp.iter_encoded())
    actual_resp = wrappers.Response.from_app(resp, req.environ, buffered=True)
    assert actual_resp.get_data() == b"FOOBAR"


def test_response_freeze():
    def generate():
        yield "foo"
        yield "bar"

    resp = wrappers.Response(generate())
    resp.freeze()
    assert resp.response == [b"foo", b"bar"]
    assert resp.headers["content-length"] == "6"


def test_response_content_length_uses_encode():
    r = wrappers.Response("你好")
    assert r.calculate_content_length() == 6


def test_other_method_payload():
    data = b"Hello World"
    req = wrappers.Request.from_values(
        input_stream=BytesIO(data),
        content_length=len(data),
        content_type="text/plain",
        method="WHAT_THE_FUCK",
    )
    assert req.get_data() == data
    assert isinstance(req.stream, LimitedStream)


def test_urlfication():
    resp = wrappers.Response()
    resp.headers["Location"] = "http://üser:pässword@☃.net/påth"
    resp.headers["Content-Location"] = "http://☃.net/"
    headers = resp.get_wsgi_headers(create_environ())
    assert headers["location"] == "http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th"
    assert headers["content-location"] == "http://xn--n3h.net/"


def test_new_response_iterator_behavior():
    req = wrappers.Request.from_values()
    resp = wrappers.Response("Hello Wörld!")

    def get_content_length(resp):
        headers = resp.get_wsgi_headers(req.environ)
        return headers.get("content-length", type=int)

    def generate_items():
        yield "Hello "
        yield "Wörld!"

    # werkzeug encodes when set to `data` now, which happens
    # if a string is passed to the response object.
    assert resp.response == ["Hello Wörld!".encode()]
    assert resp.get_data() == "Hello Wörld!".encode()
    assert get_content_length(resp) == 13
    assert not resp.is_streamed
    assert resp.is_sequence

    # try the same for manual assignment
    resp.set_data("Wörd")
    assert resp.response == ["Wörd".encode()]
    assert resp.get_data() == "Wörd".encode()
    assert get_content_length(resp) == 5
    assert not resp.is_streamed
    assert resp.is_sequence

    # automatic generator sequence conversion
    resp.response = generate_items()
    assert resp.is_streamed
    assert not resp.is_sequence
    assert resp.get_data() == "Hello Wörld!".encode()
    assert resp.response == [b"Hello ", "Wörld!".encode()]
    assert not resp.is_streamed
    assert resp.is_sequence

    # automatic generator sequence conversion
    resp.response = generate_items()
    resp.implicit_sequence_conversion = False
    assert resp.is_streamed
    assert not resp.is_sequence
    pytest.raises(RuntimeError, lambda: resp.get_data())
    resp.make_sequence()
    assert resp.get_data() == "Hello Wörld!".encode()
    assert resp.response == [b"Hello ", "Wörld!".encode()]
    assert not resp.is_streamed
    assert resp.is_sequence

    # stream makes it a list no matter how the conversion is set
    for val in True, False:
        resp.implicit_sequence_conversion = val
        resp.response = ("foo", "bar")
        assert resp.is_sequence
        resp.stream.write("baz")
        assert resp.response == ["foo", "bar", "baz"]


def test_form_data_ordering():
    class MyRequest(wrappers.Request):
        parameter_storage_class = ImmutableOrderedMultiDict

    req = MyRequest.from_values("/?foo=1&bar=0&foo=3")
    assert list(req.args) == ["foo", "bar"]
    assert list(req.args.items(multi=True)) == [
        ("foo", "1"),
        ("bar", "0"),
        ("foo", "3"),
    ]
    assert isinstance(req.args, ImmutableOrderedMultiDict)
    assert isinstance(req.values, CombinedMultiDict)
    assert req.values["foo"] == "1"
    assert req.values.getlist("foo") == ["1", "3"]


def test_values():
    r = wrappers.Request.from_values(
        method="POST", query_string={"a": "1"}, data={"a": "2", "b": "2"}
    )
    assert r.values["a"] == "1"
    assert r.values["b"] == "2"

    # form should not be combined for GET method
    r = wrappers.Request.from_values(
        method="GET", query_string={"a": "1"}, data={"a": "2", "b": "2"}
    )
    assert r.values["a"] == "1"
    assert "b" not in r.values


def test_storage_classes():
    class MyRequest(wrappers.Request):
        dict_storage_class = dict
        list_storage_class = list
        parameter_storage_class = dict

    req = MyRequest.from_values("/?foo=baz", headers={"Cookie": "foo=bar"})
    assert type(req.cookies) is dict
    assert req.cookies == {"foo": "bar"}
    assert type(req.access_route) is list

    assert type(req.args) is dict
    assert type(req.values) is CombinedMultiDict
    assert req.values["foo"] == "baz"

    req = wrappers.Request.from_values(headers={"Cookie": "foo=bar;foo=baz"})
    assert type(req.cookies) is ImmutableMultiDict
    assert req.cookies.to_dict() == {"foo": "bar"}

    # it is possible to have multiple cookies with the same name
    assert req.cookies.getlist("foo") == ["bar", "baz"]
    assert type(req.access_route) is ImmutableList

    MyRequest.list_storage_class = tuple
    req = MyRequest.from_values()
    assert type(req.access_route) is tuple


def test_response_headers_passthrough():
    headers = Headers()
    resp = wrappers.Response(headers=headers)
    assert resp.headers is headers


def test_response_304_no_content_length():
    resp = wrappers.Response("Test", status=304)
    env = create_environ()
    assert "content-length" not in resp.get_wsgi_headers(env)


def test_ranges():
    # basic range stuff
    req = wrappers.Request.from_values()
    assert req.range is None
    req = wrappers.Request.from_values(headers={"Range": "bytes=0-499"})
    assert req.range.ranges == [(0, 500)]

    resp = wrappers.Response()
    resp.content_range = req.range.make_content_range(1000)
    assert resp.content_range.units == "bytes"
    assert resp.content_range.start == 0
    assert resp.content_range.stop == 500
    assert resp.content_range.length == 1000
    assert resp.headers["Content-Range"] == "bytes 0-499/1000"

    resp.content_range.unset()
    assert "Content-Range" not in resp.headers

    resp.headers["Content-Range"] = "bytes 0-499/1000"
    assert resp.content_range.units == "bytes"
    assert resp.content_range.start == 0
    assert resp.content_range.stop == 500
    assert resp.content_range.length == 1000


def test_auto_content_length():
    resp = wrappers.Response("Hello World!")
    assert resp.content_length == 12

    resp = wrappers.Response(["Hello World!"])
    assert resp.content_length is None
    assert resp.get_wsgi_headers({})["Content-Length"] == "12"


def test_stream_content_length():
    resp = wrappers.Response()
    resp.stream.writelines(["foo", "bar", "baz"])
    assert resp.get_wsgi_headers({})["Content-Length"] == "9"

    resp = wrappers.Response()
    resp.make_conditional({"REQUEST_METHOD": "GET"})
    resp.stream.writelines(["foo", "bar", "baz"])
    assert resp.get_wsgi_headers({})["Content-Length"] == "9"

    resp = wrappers.Response("foo")
    resp.stream.writelines(["bar", "baz"])
    assert resp.get_wsgi_headers({})["Content-Length"] == "9"


def test_disabled_auto_content_length():
    class MyResponse(wrappers.Response):
        automatically_set_content_length = False

    resp = MyResponse("Hello World!")
    assert resp.content_length is None

    resp = MyResponse(["Hello World!"])
    assert resp.content_length is None
    assert "Content-Length" not in resp.get_wsgi_headers({})

    resp = MyResponse()
    resp.make_conditional({"REQUEST_METHOD": "GET"})
    assert resp.content_length is None
    assert "Content-Length" not in resp.get_wsgi_headers({})


@pytest.mark.parametrize(
    ("auto", "location", "expect"),
    (
        (False, "/test", "/test"),
        (True, "/test", "http://localhost/test"),
        (True, "test", "http://localhost/a/b/test"),
        (True, "./test", "http://localhost/a/b/test"),
        (True, "../test", "http://localhost/a/test"),
    ),
)
def test_location_header_autocorrect(monkeypatch, auto, location, expect):
    monkeypatch.setattr(wrappers.Response, "autocorrect_location_header", auto)
    env = create_environ("/a/b/c")
    resp = wrappers.Response("Hello World!")
    resp.headers["Location"] = location
    assert resp.get_wsgi_headers(env)["Location"] == expect


def test_204_and_1XX_response_has_no_content_length():
    response = wrappers.Response(status=204)
    assert response.content_length is None

    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" not in headers

    response = wrappers.Response(status=100)
    assert response.content_length is None

    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" not in headers


def test_malformed_204_response_has_no_content_length():
    # flask-restful can generate a malformed response when doing `return '', 204`
    response = wrappers.Response(status=204)
    response.set_data(b"test")
    assert response.content_length == 4

    env = create_environ()
    app_iter, status, headers = response.get_wsgi_response(env)
    assert status == "204 NO CONTENT"
    assert "Content-Length" not in headers
    assert b"".join(app_iter) == b""  # ensure data will not be sent


def test_modified_url_encoding():
    class ModifiedRequest(wrappers.Request):
        url_charset = "euc-kr"

    req = ModifiedRequest.from_values(query_string={"foo": "정상처리"}, charset="euc-kr")
    assert req.args["foo"] == "정상처리"


def test_request_method_case_sensitivity():
    req = wrappers.Request(
        {"REQUEST_METHOD": "get", "SERVER_NAME": "eggs", "SERVER_PORT": "80"}
    )
    assert req.method == "GET"


def test_write_length():
    response = wrappers.Response()
    length = response.stream.write(b"bar")
    assert length == 3


def test_stream_zip():
    import zipfile

    response = wrappers.Response()
    with contextlib.closing(zipfile.ZipFile(response.stream, mode="w")) as z:
        z.writestr("foo", b"bar")

    buffer = BytesIO(response.get_data())
    with contextlib.closing(zipfile.ZipFile(buffer, mode="r")) as z:
        assert z.namelist() == ["foo"]
        assert z.read("foo") == b"bar"


class TestSetCookie:
    def test_secure(self):
        response = wrappers.Response()
        response.set_cookie(
            "foo",
            value="bar",
            max_age=60,
            expires=0,
            path="/blub",
            domain="example.org",
            secure=True,
            samesite=None,
        )
        assert response.headers.to_wsgi_list() == [
            ("Content-Type", "text/plain; charset=utf-8"),
            (
                "Set-Cookie",
                "foo=bar; Domain=example.org;"
                " Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=60;"
                " Secure; Path=/blub",
            ),
        ]

    def test_httponly(self):
        response = wrappers.Response()
        response.set_cookie(
            "foo",
            value="bar",
            max_age=60,
            expires=0,
            path="/blub",
            domain="example.org",
            secure=False,
            httponly=True,
            samesite=None,
        )
        assert response.headers.to_wsgi_list() == [
            ("Content-Type", "text/plain; charset=utf-8"),
            (
                "Set-Cookie",
                "foo=bar; Domain=example.org;"
                " Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=60;"
                " HttpOnly; Path=/blub",
            ),
        ]

    def test_secure_and_httponly(self):
        response = wrappers.Response()
        response.set_cookie(
            "foo",
            value="bar",
            max_age=60,
            expires=0,
            path="/blub",
            domain="example.org",
            secure=True,
            httponly=True,
            samesite=None,
        )
        assert response.headers.to_wsgi_list() == [
            ("Content-Type", "text/plain; charset=utf-8"),
            (
                "Set-Cookie",
                "foo=bar; Domain=example.org;"
                " Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=60;"
                " Secure; HttpOnly; Path=/blub",
            ),
        ]

    def test_samesite(self):
        response = wrappers.Response()
        response.set_cookie(
            "foo",
            value="bar",
            max_age=60,
            expires=0,
            path="/blub",
            domain="example.org",
            secure=False,
            samesite="strict",
        )
        assert response.headers.to_wsgi_list() == [
            ("Content-Type", "text/plain; charset=utf-8"),
            (
                "Set-Cookie",
                "foo=bar; Domain=example.org;"
                " Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=60;"
                " Path=/blub; SameSite=Strict",
            ),
        ]


class TestJSON:
    def test_request(self):
        value = {"ä": "b"}
        request = wrappers.Request.from_values(json=value)
        assert request.json == value
        assert request.get_data()

    def test_response(self):
        value = {"ä": "b"}
        response = wrappers.Response(
            response=json.dumps(value), content_type="application/json"
        )
        assert response.json == value

    def test_force(self):
        value = [1, 2, 3]
        request = wrappers.Request.from_values(json=value, content_type="text/plain")
        assert request.json is None
        assert request.get_json(force=True) == value

    def test_silent(self):
        request = wrappers.Request.from_values(
            data=b'{"a":}', content_type="application/json"
        )
        assert request.get_json(silent=True) is None

        with pytest.raises(BadRequest):
            request.get_json()

    def test_cache_disabled(self):
        value = [1, 2, 3]
        request = wrappers.Request.from_values(json=value)
        assert request.get_json(cache=False) == [1, 2, 3]
        assert not request.get_data()

        with pytest.raises(BadRequest):
            request.get_json()


@pytest.mark.parametrize(
    "cls",
    [
        wrappers.BaseRequest,
        wrappers.CommonRequestDescriptorsMixin,
        wrappers.AcceptMixin,
        wrappers.ETagRequestMixin,
        wrappers.UserAgentMixin,
        wrappers.AuthorizationMixin,
        wrappers.StreamOnlyMixin,
        wrappers.PlainRequest,
        CORSRequestMixin,
        JSONMixin,
    ],
)
def test_request_mixins_deprecated(cls):
    class CheckRequest(cls, wrappers.Request):
        pass

    with pytest.warns(DeprecationWarning, match=cls.__name__):
        CheckRequest({"SERVER_NAME": "example.org", "SERVER_PORT": "80"})


@pytest.mark.parametrize(
    "cls",
    [
        wrappers.BaseResponse,
        wrappers.CommonResponseDescriptorsMixin,
        wrappers.ResponseStreamMixin,
        wrappers.ETagResponseMixin,
        wrappers.WWWAuthenticateMixin,
        CORSResponseMixin,
        JSONMixin,
    ],
)
def test_response_mixins_deprecated(cls):
    class CheckResponse(cls, wrappers.Response):
        pass

    with pytest.raises(DeprecationWarning, match=cls.__name__):
        CheckResponse()


def test_check_base_deprecated():
    with pytest.raises(DeprecationWarning, match=r"issubclass\(cls, Request\)"):
        assert issubclass(wrappers.Request, wrappers.BaseRequest)

    with pytest.raises(DeprecationWarning, match=r"isinstance\(obj, Request\)"):
        assert isinstance(
            wrappers.Request({"SERVER_NAME": "example.org", "SERVER_PORT": "80"}),
            wrappers.BaseRequest,
        )

    with pytest.raises(DeprecationWarning, match=r"issubclass\(cls, Response\)"):
        assert issubclass(wrappers.Response, wrappers.BaseResponse)

    with pytest.raises(DeprecationWarning, match=r"isinstance\(obj, Response\)"):
        assert isinstance(wrappers.Response(), wrappers.BaseResponse)


def test_response_freeze_no_etag_deprecated():
    with pytest.raises(DeprecationWarning, match="no_etag"):
        Response("Hello, World!").freeze(no_etag=True)


def test_response_coop():
    response = wrappers.Response("Hello World")
    assert response.cross_origin_opener_policy is COOP.UNSAFE_NONE
    response.cross_origin_opener_policy = COOP.SAME_ORIGIN
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"


def test_response_coep():
    response = wrappers.Response("Hello World")
    assert response.cross_origin_embedder_policy is COEP.UNSAFE_NONE
    response.cross_origin_embedder_policy = COEP.REQUIRE_CORP
    assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
