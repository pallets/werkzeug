from werkzeug._internal import _to_bytes
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import create_environ
from werkzeug.test import run_wsgi_app


def test_dispatcher():
    def null_application(environ, start_response):
        start_response("404 NOT FOUND", [("Content-Type", "text/plain")])
        yield b"NOT FOUND"

    def dummy_application(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        yield _to_bytes(environ["SCRIPT_NAME"])

    app = DispatcherMiddleware(
        null_application,
        {"/test1": dummy_application, "/test2/very": dummy_application},
    )
    tests = {
        "/test1": ("/test1", "/test1/asfd", "/test1/very"),
        "/test2/very": ("/test2/very", "/test2/very/long/path/after/script/name"),
    }

    for name, urls in tests.items():
        for p in urls:
            environ = create_environ(p)
            app_iter, status, headers = run_wsgi_app(app, environ)
            assert status == "200 OK"
            assert b"".join(app_iter).strip() == _to_bytes(name)

    app_iter, status, headers = run_wsgi_app(app, create_environ("/missing"))
    assert status == "404 NOT FOUND"
    assert b"".join(app_iter).strip() == b"NOT FOUND"
