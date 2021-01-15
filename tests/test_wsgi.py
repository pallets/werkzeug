import io
import json
import os

import pytest

from werkzeug import wsgi
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import ClientDisconnected
from werkzeug.test import Client
from werkzeug.test import create_environ
from werkzeug.test import run_wsgi_app
from werkzeug.wrappers import Response
from werkzeug.wsgi import _RangeWrapper
from werkzeug.wsgi import ClosingIterator
from werkzeug.wsgi import wrap_file


@pytest.mark.parametrize(
    ("environ", "expect"),
    (
        pytest.param({"HTTP_HOST": "spam"}, "spam", id="host"),
        pytest.param({"HTTP_HOST": "spam:80"}, "spam", id="host, strip http port"),
        pytest.param(
            {"wsgi.url_scheme": "https", "HTTP_HOST": "spam:443"},
            "spam",
            id="host, strip https port",
        ),
        pytest.param({"HTTP_HOST": "spam:8080"}, "spam:8080", id="host, custom port"),
        pytest.param(
            {"HTTP_HOST": "spam", "SERVER_NAME": "eggs", "SERVER_PORT": "80"},
            "spam",
            id="prefer host",
        ),
        pytest.param(
            {"SERVER_NAME": "eggs", "SERVER_PORT": "80"},
            "eggs",
            id="name, ignore http port",
        ),
        pytest.param(
            {"wsgi.url_scheme": "https", "SERVER_NAME": "eggs", "SERVER_PORT": "443"},
            "eggs",
            id="name, ignore https port",
        ),
        pytest.param(
            {"SERVER_NAME": "eggs", "SERVER_PORT": "8080"},
            "eggs:8080",
            id="name, custom port",
        ),
        pytest.param(
            {"HTTP_HOST": "ham", "HTTP_X_FORWARDED_HOST": "eggs"},
            "ham",
            id="ignore x-forwarded-host",
        ),
    ),
)
def test_get_host(environ, expect):
    environ.setdefault("wsgi.url_scheme", "http")
    assert wsgi.get_host(environ) == expect


def test_get_host_validate_trusted_hosts():
    env = {"SERVER_NAME": "example.org", "SERVER_PORT": "80", "wsgi.url_scheme": "http"}
    assert wsgi.get_host(env, trusted_hosts=[".example.org"]) == "example.org"
    pytest.raises(BadRequest, wsgi.get_host, env, trusted_hosts=["example.com"])
    env["SERVER_PORT"] = "8080"
    assert wsgi.get_host(env, trusted_hosts=[".example.org:8080"]) == "example.org:8080"
    pytest.raises(BadRequest, wsgi.get_host, env, trusted_hosts=[".example.com"])
    env = {"HTTP_HOST": "example.org", "wsgi.url_scheme": "http"}
    assert wsgi.get_host(env, trusted_hosts=[".example.org"]) == "example.org"
    pytest.raises(BadRequest, wsgi.get_host, env, trusted_hosts=["example.com"])


def test_responder():
    def foo(environ, start_response):
        return Response(b"Test")

    client = Client(wsgi.responder(foo))
    response = client.get("/")
    assert response.status_code == 200
    assert response.data == b"Test"


def test_pop_path_info():
    original_env = {"SCRIPT_NAME": "/foo", "PATH_INFO": "/a/b///c"}

    # regular path info popping
    def assert_tuple(script_name, path_info):
        assert env.get("SCRIPT_NAME") == script_name
        assert env.get("PATH_INFO") == path_info

    env = original_env.copy()

    def pop():
        return wsgi.pop_path_info(env)

    assert_tuple("/foo", "/a/b///c")
    assert pop() == "a"
    assert_tuple("/foo/a", "/b///c")
    assert pop() == "b"
    assert_tuple("/foo/a/b", "///c")
    assert pop() == "c"
    assert_tuple("/foo/a/b///c", "")
    assert pop() is None


def test_peek_path_info():
    env = {"SCRIPT_NAME": "/foo", "PATH_INFO": "/aaa/b///c"}

    assert wsgi.peek_path_info(env) == "aaa"
    assert wsgi.peek_path_info(env) == "aaa"
    assert wsgi.peek_path_info(env, charset=None) == b"aaa"
    assert wsgi.peek_path_info(env, charset=None) == b"aaa"


def test_path_info_and_script_name_fetching():
    env = create_environ("/\N{SNOWMAN}", "http://example.com/\N{COMET}/")
    assert wsgi.get_path_info(env) == "/\N{SNOWMAN}"
    assert wsgi.get_path_info(env, charset=None) == "/\N{SNOWMAN}".encode()
    assert wsgi.get_script_name(env) == "/\N{COMET}"
    assert wsgi.get_script_name(env, charset=None) == "/\N{COMET}".encode()


def test_query_string_fetching():
    env = create_environ("/?\N{SNOWMAN}=\N{COMET}")
    qs = wsgi.get_query_string(env)
    assert qs == "%E2%98%83=%E2%98%84"


def test_limited_stream():
    class RaisingLimitedStream(wsgi.LimitedStream):
        def on_exhausted(self):
            raise BadRequest("input stream exhausted")

    io_ = io.BytesIO(b"123456")
    stream = RaisingLimitedStream(io_, 3)
    assert stream.read() == b"123"
    pytest.raises(BadRequest, stream.read)

    io_ = io.BytesIO(b"123456")
    stream = RaisingLimitedStream(io_, 3)
    assert stream.tell() == 0
    assert stream.read(1) == b"1"
    assert stream.tell() == 1
    assert stream.read(1) == b"2"
    assert stream.tell() == 2
    assert stream.read(1) == b"3"
    assert stream.tell() == 3
    pytest.raises(BadRequest, stream.read)

    io_ = io.BytesIO(b"123456\nabcdefg")
    stream = wsgi.LimitedStream(io_, 9)
    assert stream.readline() == b"123456\n"
    assert stream.readline() == b"ab"

    io_ = io.BytesIO(b"123456\nabcdefg")
    stream = wsgi.LimitedStream(io_, 9)
    assert stream.readlines() == [b"123456\n", b"ab"]

    io_ = io.BytesIO(b"123456\nabcdefg")
    stream = wsgi.LimitedStream(io_, 9)
    assert stream.readlines(2) == [b"12"]
    assert stream.readlines(2) == [b"34"]
    assert stream.readlines() == [b"56\n", b"ab"]

    io_ = io.BytesIO(b"123456\nabcdefg")
    stream = wsgi.LimitedStream(io_, 9)
    assert stream.readline(100) == b"123456\n"

    io_ = io.BytesIO(b"123456\nabcdefg")
    stream = wsgi.LimitedStream(io_, 9)
    assert stream.readlines(100) == [b"123456\n", b"ab"]

    io_ = io.BytesIO(b"123456")
    stream = wsgi.LimitedStream(io_, 3)
    assert stream.read(1) == b"1"
    assert stream.read(1) == b"2"
    assert stream.read() == b"3"
    assert stream.read() == b""

    io_ = io.BytesIO(b"123456")
    stream = wsgi.LimitedStream(io_, 3)
    assert stream.read(-1) == b"123"

    io_ = io.BytesIO(b"123456")
    stream = wsgi.LimitedStream(io_, 0)
    assert stream.read(-1) == b""

    io_ = io.StringIO("123456")
    stream = wsgi.LimitedStream(io_, 0)
    assert stream.read(-1) == ""

    io_ = io.StringIO("123\n456\n")
    stream = wsgi.LimitedStream(io_, 8)
    assert list(stream) == ["123\n", "456\n"]


def test_limited_stream_json_load():
    stream = wsgi.LimitedStream(io.BytesIO(b'{"hello": "test"}'), 17)
    # flask.json adapts bytes to text with TextIOWrapper
    # this expects stream.readable() to exist and return true
    stream = io.TextIOWrapper(io.BufferedReader(stream), "UTF-8")
    data = json.load(stream)
    assert data == {"hello": "test"}


def test_limited_stream_disconnection():
    io_ = io.BytesIO(b"A bit of content")

    # disconnect detection on out of bytes
    stream = wsgi.LimitedStream(io_, 255)
    with pytest.raises(ClientDisconnected):
        stream.read()

    # disconnect detection because file close
    io_ = io.BytesIO(b"x" * 255)
    io_.close()
    stream = wsgi.LimitedStream(io_, 255)
    with pytest.raises(ClientDisconnected):
        stream.read()


def test_path_info_extraction():
    x = wsgi.extract_path_info("http://example.com/app", "/app/hello")
    assert x == "/hello"
    x = wsgi.extract_path_info(
        "http://example.com/app", "https://example.com/app/hello"
    )
    assert x == "/hello"
    x = wsgi.extract_path_info(
        "http://example.com/app/", "https://example.com/app/hello"
    )
    assert x == "/hello"
    x = wsgi.extract_path_info("http://example.com/app/", "https://example.com/app")
    assert x == "/"
    x = wsgi.extract_path_info("http://☃.net/", "/fööbär")
    assert x == "/fööbär"
    x = wsgi.extract_path_info("http://☃.net/x", "http://☃.net/x/fööbär")
    assert x == "/fööbär"

    env = create_environ("/fööbär", "http://☃.net/x/")
    x = wsgi.extract_path_info(env, "http://☃.net/x/fööbär")
    assert x == "/fööbär"

    x = wsgi.extract_path_info("http://example.com/app/", "https://example.com/a/hello")
    assert x is None
    x = wsgi.extract_path_info(
        "http://example.com/app/",
        "https://example.com/app/hello",
        collapse_http_schemes=False,
    )
    assert x is None


def test_get_host_fallback():
    assert (
        wsgi.get_host(
            {
                "SERVER_NAME": "foobar.example.com",
                "wsgi.url_scheme": "http",
                "SERVER_PORT": "80",
            }
        )
        == "foobar.example.com"
    )
    assert (
        wsgi.get_host(
            {
                "SERVER_NAME": "foobar.example.com",
                "wsgi.url_scheme": "http",
                "SERVER_PORT": "81",
            }
        )
        == "foobar.example.com:81"
    )


def test_get_current_url_unicode():
    env = create_environ(query_string="foo=bar&baz=blah&meh=\xcf")
    rv = wsgi.get_current_url(env)
    assert rv == "http://localhost/?foo=bar&baz=blah&meh=\xcf"


def test_get_current_url_invalid_utf8():
    env = create_environ()
    # set the query string *after* wsgi dance, so \xcf is invalid
    env["QUERY_STRING"] = "foo=bar&baz=blah&meh=\xcf"
    rv = wsgi.get_current_url(env)
    # it remains percent-encoded
    assert rv == "http://localhost/?foo=bar&baz=blah&meh=%CF"


def test_multi_part_line_breaks():
    data = "abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK"
    test_stream = io.StringIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=16))
    assert lines == ["abcdef\r\n", "ghijkl\r\n", "mnopqrstuvwxyz\r\n", "ABCDEFGHIJK"]

    data = "abc\r\nThis line is broken by the buffer length.\r\nFoo bar baz"
    test_stream = io.StringIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=24))
    assert lines == [
        "abc\r\n",
        "This line is broken by the buffer length.\r\n",
        "Foo bar baz",
    ]


def test_multi_part_line_breaks_bytes():
    data = b"abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK"
    test_stream = io.BytesIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=16))
    assert lines == [
        b"abcdef\r\n",
        b"ghijkl\r\n",
        b"mnopqrstuvwxyz\r\n",
        b"ABCDEFGHIJK",
    ]

    data = b"abc\r\nThis line is broken by the buffer length.\r\nFoo bar baz"
    test_stream = io.BytesIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=24))
    assert lines == [
        b"abc\r\n",
        b"This line is broken by the buffer length.\r\n",
        b"Foo bar baz",
    ]


def test_multi_part_line_breaks_problematic():
    data = "abc\rdef\r\nghi"
    for _ in range(1, 10):
        test_stream = io.StringIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=4))
        assert lines == ["abc\r", "def\r\n", "ghi"]


def test_iter_functions_support_iterators():
    data = ["abcdef\r\nghi", "jkl\r\nmnopqrstuvwxyz\r", "\nABCDEFGHIJK"]
    lines = list(wsgi.make_line_iter(data))
    assert lines == ["abcdef\r\n", "ghijkl\r\n", "mnopqrstuvwxyz\r\n", "ABCDEFGHIJK"]


def test_make_chunk_iter():
    data = ["abcdefXghi", "jklXmnopqrstuvwxyzX", "ABCDEFGHIJK"]
    rv = list(wsgi.make_chunk_iter(data, "X"))
    assert rv == ["abcdef", "ghijkl", "mnopqrstuvwxyz", "ABCDEFGHIJK"]

    data = "abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK"
    test_stream = io.StringIO(data)
    rv = list(wsgi.make_chunk_iter(test_stream, "X", limit=len(data), buffer_size=4))
    assert rv == ["abcdef", "ghijkl", "mnopqrstuvwxyz", "ABCDEFGHIJK"]


def test_make_chunk_iter_bytes():
    data = [b"abcdefXghi", b"jklXmnopqrstuvwxyzX", b"ABCDEFGHIJK"]
    rv = list(wsgi.make_chunk_iter(data, "X"))
    assert rv == [b"abcdef", b"ghijkl", b"mnopqrstuvwxyz", b"ABCDEFGHIJK"]

    data = b"abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK"
    test_stream = io.BytesIO(data)
    rv = list(wsgi.make_chunk_iter(test_stream, "X", limit=len(data), buffer_size=4))
    assert rv == [b"abcdef", b"ghijkl", b"mnopqrstuvwxyz", b"ABCDEFGHIJK"]

    data = b"abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK"
    test_stream = io.BytesIO(data)
    rv = list(
        wsgi.make_chunk_iter(
            test_stream, "X", limit=len(data), buffer_size=4, cap_at_buffer=True
        )
    )
    assert rv == [
        b"abcd",
        b"ef",
        b"ghij",
        b"kl",
        b"mnop",
        b"qrst",
        b"uvwx",
        b"yz",
        b"ABCD",
        b"EFGH",
        b"IJK",
    ]


def test_lines_longer_buffer_size():
    data = "1234567890\n1234567890\n"
    for bufsize in range(1, 15):
        lines = list(
            wsgi.make_line_iter(io.StringIO(data), limit=len(data), buffer_size=bufsize)
        )
        assert lines == ["1234567890\n", "1234567890\n"]


def test_lines_longer_buffer_size_cap():
    data = "1234567890\n1234567890\n"
    for bufsize in range(1, 15):
        lines = list(
            wsgi.make_line_iter(
                io.StringIO(data),
                limit=len(data),
                buffer_size=bufsize,
                cap_at_buffer=True,
            )
        )
        assert len(lines[0]) == bufsize or lines[0].endswith("\n")


def test_range_wrapper():
    response = Response(b"Hello World")
    range_wrapper = _RangeWrapper(response.response, 6, 4)
    assert next(range_wrapper) == b"Worl"

    response = Response(b"Hello World")
    range_wrapper = _RangeWrapper(response.response, 1, 0)
    with pytest.raises(StopIteration):
        next(range_wrapper)

    response = Response(b"Hello World")
    range_wrapper = _RangeWrapper(response.response, 6, 100)
    assert next(range_wrapper) == b"World"

    response = Response(x for x in (b"He", b"ll", b"o ", b"Wo", b"rl", b"d"))
    range_wrapper = _RangeWrapper(response.response, 6, 4)
    assert not range_wrapper.seekable
    assert next(range_wrapper) == b"Wo"
    assert next(range_wrapper) == b"rl"

    response = Response(x for x in (b"He", b"ll", b"o W", b"o", b"rld"))
    range_wrapper = _RangeWrapper(response.response, 6, 4)
    assert next(range_wrapper) == b"W"
    assert next(range_wrapper) == b"o"
    assert next(range_wrapper) == b"rl"
    with pytest.raises(StopIteration):
        next(range_wrapper)

    response = Response(x for x in (b"Hello", b" World"))
    range_wrapper = _RangeWrapper(response.response, 1, 1)
    assert next(range_wrapper) == b"e"
    with pytest.raises(StopIteration):
        next(range_wrapper)

    resources = os.path.join(os.path.dirname(__file__), "res")
    env = create_environ()
    with open(os.path.join(resources, "test.txt"), "rb") as f:
        response = Response(wrap_file(env, f))
        range_wrapper = _RangeWrapper(response.response, 1, 2)
        assert range_wrapper.seekable
        assert next(range_wrapper) == b"OU"
        with pytest.raises(StopIteration):
            next(range_wrapper)

    with open(os.path.join(resources, "test.txt"), "rb") as f:
        response = Response(wrap_file(env, f))
        range_wrapper = _RangeWrapper(response.response, 2)
        assert next(range_wrapper) == b"UND\n"
        with pytest.raises(StopIteration):
            next(range_wrapper)


def test_closing_iterator():
    class Namespace:
        got_close = False
        got_additional = False

    class Response:
        def __init__(self, environ, start_response):
            self.start = start_response

        # Return a generator instead of making the object its own
        # iterator. This ensures that ClosingIterator calls close on
        # the iterable (the object), not the iterator.
        def __iter__(self):
            self.start("200 OK", [("Content-Type", "text/plain")])
            yield "some content"

        def close(self):
            Namespace.got_close = True

    def additional():
        Namespace.got_additional = True

    def app(environ, start_response):
        return ClosingIterator(Response(environ, start_response), additional)

    app_iter, status, headers = run_wsgi_app(app, create_environ(), buffered=True)

    assert "".join(app_iter) == "some content"
    assert Namespace.got_close
    assert Namespace.got_additional
