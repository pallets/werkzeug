# -*- coding: utf-8 -*-
import pytest

from werkzeug.middleware.lint import HTTPWarning
from werkzeug.middleware.lint import LintMiddleware
from werkzeug.middleware.lint import WSGIWarning
from werkzeug.test import create_environ
from werkzeug.test import run_wsgi_app


def dummy_application(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return ["Foo"]


def test_lint_middleware():
    """ Test lint middleware runs for a dummy applications without warnings """
    app = LintMiddleware(dummy_application)

    environ = create_environ("/test")
    app_iter, status, headers = run_wsgi_app(app, environ, buffered=True)
    assert status == "200 OK"


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("wsgi.version", (0, 7), "Environ is not a WSGI 1.0 environ."),
        ("SCRIPT_NAME", "test", "'SCRIPT_NAME' does not start with a slash:"),
        ("PATH_INFO", "test", "'PATH_INFO' does not start with a slash:"),
    ],
)
def test_lint_middleware_check_environ(key, value, message):
    app = LintMiddleware(dummy_application)

    environ = create_environ("/test")
    environ[key] = value
    with pytest.warns(WSGIWarning, match=message):
        app_iter, status, headers = run_wsgi_app(app, environ, buffered=True)
    assert status == "200 OK"


def test_lint_middleware_invalid_status():
    def my_dummy_application(environ, start_response):
        start_response("20 OK", [("Content-Type", "text/plain")])
        return ["Foo"]

    app = LintMiddleware(my_dummy_application)

    environ = create_environ("/test")
    with pytest.warns(WSGIWarning) as record:
        run_wsgi_app(app, environ, buffered=True)

    # Returning status 20 should raise three different warnings
    assert len(record) == 3


@pytest.mark.parametrize(
    "headers, message",
    [
        (tuple([("Content-Type", "text/plain")]), "header list is not a list"),
        (["fo"], "Headers must tuple 2-item tuples"),
        ([("status", "foo")], "The status header is not supported"),
    ],
)
def test_lint_middleware_http_headers(headers, message):
    def my_dummy_application(environ, start_response):
        start_response("200 OK", headers)
        return ["Foo"]

    app = LintMiddleware(my_dummy_application)

    environ = create_environ("/test")
    with pytest.warns(WSGIWarning, match=message):
        run_wsgi_app(app, environ, buffered=True)


def test_lint_middleware_invalid_location():
    def my_dummy_application(environ, start_response):
        start_response("200 OK", [("location", "foo")])
        return ["Foo"]

    app = LintMiddleware(my_dummy_application)

    environ = create_environ("/test")
    with pytest.warns(HTTPWarning, match="absolute URLs required for location header"):
        run_wsgi_app(app, environ, buffered=True)
