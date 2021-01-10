import pytest

from werkzeug.middleware.http_proxy import ProxyMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_http_proxy(standard_app):
    app = ProxyMiddleware(
        Response("ROOT"),
        {
            "/foo": {
                "target": standard_app.url,
                "host": "faked.invalid",
                "headers": {"X-Special": "foo"},
            },
            "/bar": {
                "target": standard_app.url,
                "host": None,
                "remove_prefix": True,
                "headers": {"X-Special": "bar"},
            },
            "/autohost": {"target": standard_app.url},
        },
    )

    client = Client(app)

    r = client.get("/")
    assert r.data == b"ROOT"

    r = client.get("/foo/bar")
    assert r.json["HTTP_X_SPECIAL"] == "foo"
    assert r.json["HTTP_HOST"] == "faked.invalid"
    assert r.json["PATH_INFO"] == "/foo/bar"

    r = client.get("/bar/baz?a=a&b=b")
    assert r.json["HTTP_X_SPECIAL"] == "bar"
    assert r.json["HTTP_HOST"] == "localhost"
    assert r.json["PATH_INFO"] == "/baz"
    assert r.json["QUERY_STRING"] == "a=a&b=b"

    r = client.get("/autohost/aha")
    assert "HTTP_X_SPECIAL" not in r.json
    assert r.json["HTTP_HOST"] == "127.0.0.1"
    assert r.json["PATH_INFO"] == "/autohost/aha"
