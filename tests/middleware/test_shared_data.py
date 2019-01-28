# -*- coding: utf-8 -*-
import os
from contextlib import closing

from werkzeug._compat import to_native
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.test import create_environ
from werkzeug.test import run_wsgi_app


def test_get_file_loader():
    app = SharedDataMiddleware(None, {})
    assert callable(app.get_file_loader("foo"))


def test_shared_data_middleware(tmpdir):
    def null_application(environ, start_response):
        start_response("404 NOT FOUND", [("Content-Type", "text/plain")])
        yield b"NOT FOUND"

    test_dir = str(tmpdir)

    with open(os.path.join(test_dir, to_native(u"äöü", "utf-8")), "w") as test_file:
        test_file.write(u"FOUND")

    for t in [list, dict]:
        app = SharedDataMiddleware(
            null_application,
            t(
                [
                    ("/", os.path.join(os.path.dirname(__file__), "..", "res")),
                    ("/sources", os.path.join(os.path.dirname(__file__), "..", "res")),
                    ("/pkg", ("werkzeug.debug", "shared")),
                    ("/foo", test_dir),
                ]
            ),
        )

        for p in "/test.txt", "/sources/test.txt", "/foo/äöü":
            app_iter, status, headers = run_wsgi_app(app, create_environ(p))
            assert status == "200 OK"

            with closing(app_iter) as app_iter:
                data = b"".join(app_iter).strip()

            assert data == b"FOUND"

        app_iter, status, headers = run_wsgi_app(
            app, create_environ("/pkg/debugger.js")
        )

        with closing(app_iter) as app_iter:
            contents = b"".join(app_iter)

        assert b"$(function() {" in contents

        app_iter, status, headers = run_wsgi_app(app, create_environ("/missing"))
        assert status == "404 NOT FOUND"
        assert b"".join(app_iter).strip() == b"NOT FOUND"
