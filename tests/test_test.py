# -*- coding: utf-8 -*-
"""
    tests.test
    ~~~~~~~~~~

    Tests the testing tools.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import json
import sys
from functools import partial
from io import BytesIO

import pytest

from . import strict_eq
from werkzeug._compat import implements_iterator
from werkzeug._compat import iteritems
from werkzeug._compat import to_bytes
from werkzeug.datastructures import FileStorage
from werkzeug.datastructures import MultiDict
from werkzeug.formparser import parse_form_data
from werkzeug.test import Client
from werkzeug.test import ClientRedirectError
from werkzeug.test import create_environ
from werkzeug.test import EnvironBuilder
from werkzeug.test import run_wsgi_app
from werkzeug.test import stream_encode_multipart
from werkzeug.utils import redirect
from werkzeug.wrappers import BaseResponse
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response
from werkzeug.wsgi import pop_path_info


def cookie_app(environ, start_response):
    """A WSGI application which sets a cookie, and returns as a response any
    cookie which exists.
    """
    response = Response(environ.get("HTTP_COOKIE", "No Cookie"), mimetype="text/plain")
    response.set_cookie("test", "test")
    return response(environ, start_response)


def redirect_loop_app(environ, start_response):
    response = redirect("http://localhost/some/redirect/")
    return response(environ, start_response)


def redirect_with_get_app(environ, start_response):
    req = Request(environ)
    if req.url not in (
        "http://localhost/",
        "http://localhost/first/request",
        "http://localhost/some/redirect/",
    ):
        raise AssertionError('redirect_demo_app() did not expect URL "%s"' % req.url)
    if "/some/redirect" not in req.url:
        response = redirect("http://localhost/some/redirect/")
    else:
        response = Response("current url: %s" % req.url)
    return response(environ, start_response)


def external_redirect_demo_app(environ, start_response):
    response = redirect("http://example.com/")
    return response(environ, start_response)


def external_subdomain_redirect_demo_app(environ, start_response):
    if "test.example.com" in environ["HTTP_HOST"]:
        response = Response("redirected successfully to subdomain")
    else:
        response = redirect("http://test.example.com/login")
    return response(environ, start_response)


def multi_value_post_app(environ, start_response):
    req = Request(environ)
    assert req.form["field"] == "val1", req.form["field"]
    assert req.form.getlist("field") == ["val1", "val2"], req.form.getlist("field")
    response = Response("ok")
    return response(environ, start_response)


def test_cookie_forging():
    c = Client(cookie_app)
    c.set_cookie("localhost", "foo", "bar")
    appiter, code, headers = c.open()
    strict_eq(list(appiter), [b"foo=bar"])


def test_set_cookie_app():
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert "Set-Cookie" in dict(headers)


def test_cookiejar_stores_cookie():
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert "test" in c.cookie_jar._cookies["localhost.local"]["/"]


def test_no_initial_cookie():
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    strict_eq(b"".join(appiter), b"No Cookie")


def test_resent_cookie():
    c = Client(cookie_app)
    c.open()
    appiter, code, headers = c.open()
    strict_eq(b"".join(appiter), b"test=test")


def test_disable_cookies():
    c = Client(cookie_app, use_cookies=False)
    c.open()
    appiter, code, headers = c.open()
    strict_eq(b"".join(appiter), b"No Cookie")


def test_cookie_for_different_path():
    c = Client(cookie_app)
    c.open("/path1")
    appiter, code, headers = c.open("/path2")
    strict_eq(b"".join(appiter), b"test=test")


def test_environ_builder_basics():
    b = EnvironBuilder()
    assert b.content_type is None
    b.method = "POST"
    assert b.content_type is None
    b.form["test"] = "normal value"
    assert b.content_type == "application/x-www-form-urlencoded"
    b.files.add_file("test", BytesIO(b"test contents"), "test.txt")
    assert b.files["test"].content_type == "text/plain"
    b.form["test_int"] = 1
    assert b.content_type == "multipart/form-data"

    req = b.get_request()
    b.close()

    strict_eq(req.url, u"http://localhost/")
    strict_eq(req.method, "POST")
    strict_eq(req.form["test"], u"normal value")
    assert req.files["test"].content_type == "text/plain"
    strict_eq(req.files["test"].filename, u"test.txt")
    strict_eq(req.files["test"].read(), b"test contents")


def test_environ_builder_data():
    b = EnvironBuilder(data="foo")
    assert b.input_stream.getvalue() == b"foo"
    b = EnvironBuilder(data=b"foo")
    assert b.input_stream.getvalue() == b"foo"

    b = EnvironBuilder(data={"foo": "bar"})
    assert b.form["foo"] == "bar"
    b = EnvironBuilder(data={"foo": ["bar1", "bar2"]})
    assert b.form.getlist("foo") == ["bar1", "bar2"]

    def check_list_content(b, length):
        foo = b.files.getlist("foo")
        assert len(foo) == length
        for obj in foo:
            assert isinstance(obj, FileStorage)

    b = EnvironBuilder(data={"foo": BytesIO()})
    check_list_content(b, 1)
    b = EnvironBuilder(data={"foo": [BytesIO(), BytesIO()]})
    check_list_content(b, 2)

    b = EnvironBuilder(data={"foo": (BytesIO(),)})
    check_list_content(b, 1)
    b = EnvironBuilder(data={"foo": [(BytesIO(),), (BytesIO(),)]})
    check_list_content(b, 2)


def test_environ_builder_json():
    @Request.application
    def app(request):
        assert request.content_type == "application/json"
        return Response(json.loads(request.get_data(as_text=True))["foo"])

    c = Client(app, Response)
    response = c.post("/", json={"foo": "bar"})
    assert response.data == b"bar"

    with pytest.raises(TypeError):
        c.post("/", json={"foo": "bar"}, data={"baz": "qux"})


def test_environ_builder_headers():
    b = EnvironBuilder(
        environ_base={"HTTP_USER_AGENT": "Foo/0.1"},
        environ_overrides={"wsgi.version": (1, 1)},
    )
    b.headers["X-Beat-My-Horse"] = "very well sir"
    env = b.get_environ()
    strict_eq(env["HTTP_USER_AGENT"], "Foo/0.1")
    strict_eq(env["HTTP_X_BEAT_MY_HORSE"], "very well sir")
    strict_eq(env["wsgi.version"], (1, 1))

    b.headers["User-Agent"] = "Bar/1.0"
    env = b.get_environ()
    strict_eq(env["HTTP_USER_AGENT"], "Bar/1.0")


def test_environ_builder_headers_content_type():
    b = EnvironBuilder(headers={"Content-Type": "text/plain"})
    env = b.get_environ()
    assert env["CONTENT_TYPE"] == "text/plain"
    b = EnvironBuilder(content_type="text/html", headers={"Content-Type": "text/plain"})
    env = b.get_environ()
    assert env["CONTENT_TYPE"] == "text/html"
    b = EnvironBuilder()
    env = b.get_environ()
    assert "CONTENT_TYPE" not in env


def test_environ_builder_paths():
    b = EnvironBuilder(path="/foo", base_url="http://example.com/")
    strict_eq(b.base_url, "http://example.com/")
    strict_eq(b.path, "/foo")
    strict_eq(b.script_root, "")
    strict_eq(b.host, "example.com")

    b = EnvironBuilder(path="/foo", base_url="http://example.com/bar")
    strict_eq(b.base_url, "http://example.com/bar/")
    strict_eq(b.path, "/foo")
    strict_eq(b.script_root, "/bar")
    strict_eq(b.host, "example.com")

    b.host = "localhost"
    strict_eq(b.base_url, "http://localhost/bar/")
    b.base_url = "http://localhost:8080/"
    strict_eq(b.host, "localhost:8080")
    strict_eq(b.server_name, "localhost")
    strict_eq(b.server_port, 8080)

    b.host = "foo.invalid"
    b.url_scheme = "https"
    b.script_root = "/test"
    env = b.get_environ()
    strict_eq(env["SERVER_NAME"], "foo.invalid")
    strict_eq(env["SERVER_PORT"], "443")
    strict_eq(env["SCRIPT_NAME"], "/test")
    strict_eq(env["PATH_INFO"], "/foo")
    strict_eq(env["HTTP_HOST"], "foo.invalid")
    strict_eq(env["wsgi.url_scheme"], "https")
    strict_eq(b.base_url, "https://foo.invalid/test/")


def test_environ_builder_content_type():
    builder = EnvironBuilder()
    assert builder.content_type is None
    builder.method = "POST"
    assert builder.content_type is None
    builder.method = "PUT"
    assert builder.content_type is None
    builder.method = "PATCH"
    assert builder.content_type is None
    builder.method = "DELETE"
    assert builder.content_type is None
    builder.method = "GET"
    assert builder.content_type is None
    builder.form["foo"] = "bar"
    assert builder.content_type == "application/x-www-form-urlencoded"
    builder.files.add_file("blafasel", BytesIO(b"foo"), "test.txt")
    assert builder.content_type == "multipart/form-data"
    req = builder.get_request()
    strict_eq(req.form["foo"], u"bar")
    strict_eq(req.files["blafasel"].read(), b"foo")


def test_environ_builder_stream_switch():
    d = MultiDict(dict(foo=u"bar", blub=u"blah", hu=u"hum"))
    for use_tempfile in False, True:
        stream, length, boundary = stream_encode_multipart(
            d, use_tempfile, threshold=150
        )
        assert isinstance(stream, BytesIO) != use_tempfile

        form = parse_form_data(
            {
                "wsgi.input": stream,
                "CONTENT_LENGTH": str(length),
                "CONTENT_TYPE": 'multipart/form-data; boundary="%s"' % boundary,
            }
        )[1]
        strict_eq(form, d)
        stream.close()


def test_environ_builder_unicode_file_mix():
    for use_tempfile in False, True:
        f = FileStorage(BytesIO(u"\N{SNOWMAN}".encode("utf-8")), "snowman.txt")
        d = MultiDict(dict(f=f, s=u"\N{SNOWMAN}"))
        stream, length, boundary = stream_encode_multipart(
            d, use_tempfile, threshold=150
        )
        assert isinstance(stream, BytesIO) != use_tempfile

        _, form, files = parse_form_data(
            {
                "wsgi.input": stream,
                "CONTENT_LENGTH": str(length),
                "CONTENT_TYPE": 'multipart/form-data; boundary="%s"' % boundary,
            }
        )
        strict_eq(form["s"], u"\N{SNOWMAN}")
        strict_eq(files["f"].name, "f")
        strict_eq(files["f"].filename, u"snowman.txt")
        strict_eq(files["f"].read(), u"\N{SNOWMAN}".encode("utf-8"))
        stream.close()


def test_create_environ():
    env = create_environ("/foo?bar=baz", "http://example.org/")
    expected = {
        "wsgi.multiprocess": False,
        "wsgi.version": (1, 0),
        "wsgi.run_once": False,
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.url_scheme": "http",
        "SCRIPT_NAME": "",
        "SERVER_NAME": "example.org",
        "REQUEST_METHOD": "GET",
        "HTTP_HOST": "example.org",
        "PATH_INFO": "/foo",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "QUERY_STRING": "bar=baz",
    }
    for key, value in iteritems(expected):
        assert env[key] == value
    strict_eq(env["wsgi.input"].read(0), b"")
    strict_eq(create_environ("/foo", "http://example.com/")["SCRIPT_NAME"], "")


def test_create_environ_query_string_error():
    with pytest.raises(ValueError):
        create_environ("/foo?bar=baz", query_string={"a": "b"})


def test_builder_from_environ():
    environ = create_environ(
        "/foo",
        base_url="https://example.com/base",
        query_string={"name": "Werkzeug"},
        data={"foo": "bar"},
        headers={"X-Foo": "bar"},
    )
    builder = EnvironBuilder.from_environ(environ)
    try:
        new_environ = builder.get_environ()
    finally:
        builder.close()
    assert new_environ == environ


def test_file_closing():
    closed = []

    class SpecialInput(object):
        def read(self, size):
            return ""

        def close(self):
            closed.append(self)

    create_environ(data={"foo": SpecialInput()})
    strict_eq(len(closed), 1)
    builder = EnvironBuilder()
    builder.files.add_file("blah", SpecialInput())
    builder.close()
    strict_eq(len(closed), 2)


def test_follow_redirect():
    env = create_environ("/", base_url="http://localhost")
    c = Client(redirect_with_get_app)
    appiter, code, headers = c.open(environ_overrides=env, follow_redirects=True)
    strict_eq(code, "200 OK")
    strict_eq(b"".join(appiter), b"current url: http://localhost/some/redirect/")

    # Test that the :cls:`Client` is aware of user defined response wrappers
    c = Client(redirect_with_get_app, response_wrapper=BaseResponse)
    resp = c.get("/", follow_redirects=True)
    strict_eq(resp.status_code, 200)
    strict_eq(resp.data, b"current url: http://localhost/some/redirect/")

    # test with URL other than '/' to make sure redirected URL's are correct
    c = Client(redirect_with_get_app, response_wrapper=BaseResponse)
    resp = c.get("/first/request", follow_redirects=True)
    strict_eq(resp.status_code, 200)
    strict_eq(resp.data, b"current url: http://localhost/some/redirect/")


def test_follow_local_redirect():
    class LocalResponse(BaseResponse):
        autocorrect_location_header = False

    def local_redirect_app(environ, start_response):
        req = Request(environ)
        if "/from/location" in req.url:
            response = redirect("/to/location", Response=LocalResponse)
        else:
            response = Response("current path: %s" % req.path)
        return response(environ, start_response)

    c = Client(local_redirect_app, response_wrapper=BaseResponse)
    resp = c.get("/from/location", follow_redirects=True)
    strict_eq(resp.status_code, 200)
    strict_eq(resp.data, b"current path: /to/location")


@pytest.mark.parametrize(
    ("code", "keep"), ((302, False), (301, False), (307, True), (308, True))
)
def test_follow_redirect_body(code, keep):
    @Request.application
    def app(request):
        if request.url == "http://localhost/some/redirect/":
            assert request.method == "POST" if keep else "GET"
            assert request.headers["X-Foo"] == "bar"

            if keep:
                assert request.form["foo"] == "bar"
            else:
                assert not request.form

            return Response("current url: %s" % request.url)

        return redirect("http://localhost/some/redirect/", code=code)

    c = Client(app, response_wrapper=BaseResponse)
    response = c.post(
        "/", follow_redirects=True, data={"foo": "bar"}, headers={"X-Foo": "bar"}
    )
    assert response.status_code == 200
    assert response.data == b"current url: http://localhost/some/redirect/"


def test_follow_external_redirect():
    env = create_environ("/", base_url="http://localhost")
    c = Client(external_redirect_demo_app)
    pytest.raises(
        RuntimeError, lambda: c.get(environ_overrides=env, follow_redirects=True)
    )


def test_follow_external_redirect_on_same_subdomain():
    env = create_environ("/", base_url="http://example.com")
    c = Client(external_subdomain_redirect_demo_app, allow_subdomain_redirects=True)
    c.get(environ_overrides=env, follow_redirects=True)

    # check that this does not work for real external domains
    env = create_environ("/", base_url="http://localhost")
    pytest.raises(
        RuntimeError, lambda: c.get(environ_overrides=env, follow_redirects=True)
    )

    # check that subdomain redirects fail if no `allow_subdomain_redirects` is applied
    c = Client(external_subdomain_redirect_demo_app)
    pytest.raises(
        RuntimeError, lambda: c.get(environ_overrides=env, follow_redirects=True)
    )


def test_follow_redirect_loop():
    c = Client(redirect_loop_app, response_wrapper=BaseResponse)
    with pytest.raises(ClientRedirectError):
        c.get("/", follow_redirects=True)


def test_follow_redirect_non_root_base_url():
    @Request.application
    def app(request):
        if request.path == "/redirect":
            return redirect("done")

        return Response(request.path)

    c = Client(app, response_wrapper=Response)
    response = c.get(
        "/redirect", base_url="http://localhost/other", follow_redirects=True
    )
    assert response.data == b"/done"


def test_follow_redirect_exhaust_intermediate():
    class Middleware(object):
        def __init__(self, app):
            self.app = app
            self.active = 0

        def __call__(self, environ, start_response):
            # Test client must exhaust response stream, otherwise the
            # cleanup code that decrements this won't have run by the
            # time the next request is started.
            assert not self.active
            self.active += 1
            try:
                for chunk in self.app(environ, start_response):
                    yield chunk
            finally:
                self.active -= 1

    app = Middleware(redirect_with_get_app)
    client = Client(Middleware(redirect_with_get_app), Response)
    response = client.get("/", follow_redirects=True, buffered=False)
    assert response.data == b"current url: http://localhost/some/redirect/"
    assert not app.active


def test_cookie_across_redirect():
    @Request.application
    def app(request):
        if request.path == "/":
            return Response(request.cookies.get("auth", "out"))

        if request.path == "/in":
            rv = redirect("/")
            rv.set_cookie("auth", "in")
            return rv

        if request.path == "/out":
            rv = redirect("/")
            rv.delete_cookie("auth")
            return rv

    c = Client(app, Response)
    assert c.get("/").data == b"out"
    assert c.get("/in", follow_redirects=True).data == b"in"
    assert c.get("/").data == b"in"
    assert c.get("/out", follow_redirects=True).data == b"out"
    assert c.get("/").data == b"out"


def test_redirect_mutate_environ():
    @Request.application
    def app(request):
        if request.path == "/first":
            return redirect("/prefix/second")

        return Response(request.path)

    def middleware(environ, start_response):
        # modify the environ in place, shouldn't propagate to redirect request
        pop_path_info(environ)
        return app(environ, start_response)

    c = Client(middleware, Response)
    rv = c.get("/prefix/first", follow_redirects=True)
    # if modified environ was used by client, this would be /
    assert rv.data == b"/second"


def test_path_info_script_name_unquoting():
    def test_app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [environ["PATH_INFO"] + "\n" + environ["SCRIPT_NAME"]]

    c = Client(test_app, response_wrapper=BaseResponse)
    resp = c.get("/foo%40bar")
    strict_eq(resp.data, b"/foo@bar\n")
    c = Client(test_app, response_wrapper=BaseResponse)
    resp = c.get("/foo%40bar", "http://localhost/bar%40baz")
    strict_eq(resp.data, b"/foo@bar\n/bar@baz")


def test_multi_value_submit():
    c = Client(multi_value_post_app, response_wrapper=BaseResponse)
    data = {"field": ["val1", "val2"]}
    resp = c.post("/", data=data)
    strict_eq(resp.status_code, 200)
    c = Client(multi_value_post_app, response_wrapper=BaseResponse)
    data = MultiDict({"field": ["val1", "val2"]})
    resp = c.post("/", data=data)
    strict_eq(resp.status_code, 200)


def test_iri_support():
    b = EnvironBuilder(u"/föö-bar", base_url=u"http://☃.net/")
    strict_eq(b.path, "/f%C3%B6%C3%B6-bar")
    strict_eq(b.base_url, "http://xn--n3h.net/")


@pytest.mark.parametrize("buffered", (True, False))
@pytest.mark.parametrize("iterable", (True, False))
def test_run_wsgi_apps(buffered, iterable):
    leaked_data = []

    def simple_app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/html")])
        return ["Hello World!"]

    def yielding_app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/html")])
        yield "Hello "
        yield "World!"

    def late_start_response(environ, start_response):
        yield "Hello "
        yield "World"
        start_response("200 OK", [("Content-Type", "text/html")])
        yield "!"

    def depends_on_close(environ, start_response):
        leaked_data.append("harhar")
        start_response("200 OK", [("Content-Type", "text/html")])

        class Rv(object):
            def __iter__(self):
                yield "Hello "
                yield "World"
                yield "!"

            def close(self):
                assert leaked_data.pop() == "harhar"

        return Rv()

    for app in (simple_app, yielding_app, late_start_response, depends_on_close):
        if iterable:
            app = iterable_middleware(app)
        app_iter, status, headers = run_wsgi_app(app, {}, buffered=buffered)
        strict_eq(status, "200 OK")
        strict_eq(list(headers), [("Content-Type", "text/html")])
        strict_eq("".join(app_iter), "Hello World!")

        if hasattr(app_iter, "close"):
            app_iter.close()
        assert not leaked_data


@pytest.mark.parametrize("buffered", (True, False))
@pytest.mark.parametrize("iterable", (True, False))
def test_lazy_start_response_empty_response_app(buffered, iterable):
    @implements_iterator
    class app:
        def __init__(self, environ, start_response):
            self.start_response = start_response

        def __iter__(self):
            return self

        def __next__(self):
            self.start_response("200 OK", [("Content-Type", "text/html")])
            raise StopIteration

    if iterable:
        app = iterable_middleware(app)
    app_iter, status, headers = run_wsgi_app(app, {}, buffered=buffered)
    strict_eq(status, "200 OK")
    strict_eq(list(headers), [("Content-Type", "text/html")])
    strict_eq("".join(app_iter), "")


def test_run_wsgi_app_closing_iterator():
    got_close = []

    @implements_iterator
    class CloseIter(object):
        def __init__(self):
            self.iterated = False

        def __iter__(self):
            return self

        def close(self):
            got_close.append(None)

        def __next__(self):
            if self.iterated:
                raise StopIteration()
            self.iterated = True
            return "bar"

    def bar(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return CloseIter()

    app_iter, status, headers = run_wsgi_app(bar, {})
    assert status == "200 OK"
    assert list(headers) == [("Content-Type", "text/plain")]
    assert next(app_iter) == "bar"
    pytest.raises(StopIteration, partial(next, app_iter))
    app_iter.close()

    assert run_wsgi_app(bar, {}, True)[0] == ["bar"]

    assert len(got_close) == 2


def iterable_middleware(app):
    """Guarantee that the app returns an iterable"""

    def inner(environ, start_response):
        rv = app(environ, start_response)

        class Iterable(object):
            def __iter__(self):
                return iter(rv)

            if hasattr(rv, "close"):

                def close(self):
                    rv.close()

        return Iterable()

    return inner


def test_multiple_cookies():
    @Request.application
    def test_app(request):
        response = Response(repr(sorted(request.cookies.items())))
        response.set_cookie(u"test1", b"foo")
        response.set_cookie(u"test2", b"bar")
        return response

    client = Client(test_app, Response)
    resp = client.get("/")
    strict_eq(resp.data, b"[]")
    resp = client.get("/")
    strict_eq(
        resp.data, to_bytes(repr([("test1", u"foo"), ("test2", u"bar")]), "ascii")
    )


def test_correct_open_invocation_on_redirect():
    class MyClient(Client):
        counter = 0

        def open(self, *args, **kwargs):
            self.counter += 1
            env = kwargs.setdefault("environ_overrides", {})
            env["werkzeug._foo"] = self.counter
            return Client.open(self, *args, **kwargs)

    @Request.application
    def test_app(request):
        return Response(str(request.environ["werkzeug._foo"]))

    c = MyClient(test_app, response_wrapper=Response)
    strict_eq(c.get("/").data, b"1")
    strict_eq(c.get("/").data, b"2")
    strict_eq(c.get("/").data, b"3")


def test_correct_encoding():
    req = Request.from_values(u"/\N{SNOWMAN}", u"http://example.com/foo")
    strict_eq(req.script_root, u"/foo")
    strict_eq(req.path, u"/\N{SNOWMAN}")


def test_full_url_requests_with_args():
    base = "http://example.com/"

    @Request.application
    def test_app(request):
        return Response(request.args["x"])

    client = Client(test_app, Response)
    resp = client.get("/?x=42", base)
    strict_eq(resp.data, b"42")
    resp = client.get("http://www.example.com/?x=23", base)
    strict_eq(resp.data, b"23")


def test_delete_requests_with_form():
    @Request.application
    def test_app(request):
        return Response(request.form.get("x", None))

    client = Client(test_app, Response)
    resp = client.delete("/", data={"x": 42})
    strict_eq(resp.data, b"42")


def test_post_with_file_descriptor(tmpdir):
    c = Client(Response(), response_wrapper=Response)
    f = tmpdir.join("some-file.txt")
    f.write("foo")
    with open(f.strpath, mode="rt") as data:
        resp = c.post("/", data=data)
    strict_eq(resp.status_code, 200)
    with open(f.strpath, mode="rb") as data:
        resp = c.post("/", data=data)
    strict_eq(resp.status_code, 200)


def test_content_type():
    @Request.application
    def test_app(request):
        return Response(request.content_type)

    client = Client(test_app, Response)

    resp = client.get("/", data=b"testing", mimetype="text/css")
    strict_eq(resp.data, b"text/css; charset=utf-8")

    resp = client.get("/", data=b"testing", mimetype="application/octet-stream")
    strict_eq(resp.data, b"application/octet-stream")


def test_raw_request_uri():
    @Request.application
    def app(request):
        path_info = request.path
        request_uri = request.environ["REQUEST_URI"]
        return Response("\n".join((path_info, request_uri)))

    client = Client(app, Response)
    response = client.get("/hello%2fworld")
    data = response.get_data(as_text=True)
    assert data == "/hello/world\n/hello%2fworld"
