from werkzeug.middleware.http_proxy import ProxyMiddleware
from werkzeug.test import Client
from werkzeug.urls import url_parse
from werkzeug.wrappers import BaseResponse


def test_http_proxy(dev_server):
    server = dev_server(
        """
        from werkzeug.wrappers import Request, Response

        @Request.application
        def app(request):
            special = request.headers.get("X-Special")
            host = request.environ["HTTP_HOST"]
            return Response(f"{special}|{host}|{request.full_path}")
        """
    )

    app = ProxyMiddleware(
        BaseResponse("ROOT"),
        {
            "/foo": {
                "target": server.url,
                "host": "faked.invalid",
                "headers": {"X-Special": "foo"},
            },
            "/bar": {
                "target": server.url,
                "host": None,
                "remove_prefix": True,
                "headers": {"X-Special": "bar"},
            },
            "/autohost": {"target": server.url},
        },
    )

    client = Client(app, response_wrapper=BaseResponse)

    rv = client.get("/")
    assert rv.data == b"ROOT"

    rv = client.get("/foo/bar")
    assert rv.data.decode("ascii") == "foo|faked.invalid|/foo/bar?"

    rv = client.get("/bar/baz")
    assert rv.data.decode("ascii") == "bar|localhost|/baz?"

    rv = client.get("/autohost/aha")
    expected = f"None|{url_parse(server.url).ascii_host}|/autohost/aha?"
    assert rv.data.decode("ascii") == expected

    # test query string
    rv = client.get("/bar/baz?a=a&b=b")
    assert rv.data.decode("ascii") == "bar|localhost|/baz?a=a&b=b"
