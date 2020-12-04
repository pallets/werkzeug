import pytest

from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import Map
from werkzeug.routing import Rule
from werkzeug.test import Client
from werkzeug.test import create_environ
from werkzeug.utils import redirect
from werkzeug.wrappers import Request


@pytest.mark.parametrize(
    ("kwargs", "base", "url_root"),
    (
        pytest.param(
            {},
            {
                "REMOTE_ADDR": "192.168.0.2",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.1",
                "HTTP_X_FORWARDED_PROTO": "https",
            },
            "https://spam/",
            id="for",
        ),
        pytest.param(
            {"x_proto": 1},
            {"HTTP_HOST": "spam", "HTTP_X_FORWARDED_PROTO": "https"},
            "https://spam/",
            id="proto",
        ),
        pytest.param(
            {"x_host": 1},
            {"HTTP_HOST": "spam", "HTTP_X_FORWARDED_HOST": "eggs"},
            "http://eggs/",
            id="host",
        ),
        pytest.param(
            {"x_port": 1},
            {"HTTP_HOST": "spam", "HTTP_X_FORWARDED_PORT": "8080"},
            "http://spam:8080/",
            id="port, host without port",
        ),
        pytest.param(
            {"x_port": 1},
            {"HTTP_HOST": "spam:9000", "HTTP_X_FORWARDED_PORT": "8080"},
            "http://spam:8080/",
            id="port, host with port",
        ),
        pytest.param(
            {"x_port": 1},
            {
                "SERVER_NAME": "spam",
                "SERVER_PORT": "9000",
                "HTTP_X_FORWARDED_PORT": "8080",
            },
            "http://spam:8080/",
            id="port, name",
        ),
        pytest.param(
            {"x_prefix": 1},
            {"HTTP_HOST": "spam", "HTTP_X_FORWARDED_PREFIX": "/eggs"},
            "http://spam/eggs/",
            id="prefix",
        ),
        pytest.param(
            {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1},
            {
                "REMOTE_ADDR": "192.168.0.2",
                "HTTP_HOST": "spam:9000",
                "HTTP_X_FORWARDED_FOR": "192.168.0.1",
                "HTTP_X_FORWARDED_PROTO": "https",
                "HTTP_X_FORWARDED_HOST": "eggs",
                "HTTP_X_FORWARDED_PORT": "443",
                "HTTP_X_FORWARDED_PREFIX": "/ham",
            },
            "https://eggs/ham/",
            id="all",
        ),
        pytest.param(
            {"x_for": 2},
            {
                "REMOTE_ADDR": "192.168.0.3",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.1, 192.168.0.2",
            },
            "http://spam/",
            id="multiple for",
        ),
        pytest.param(
            {"x_for": 0},
            {
                "REMOTE_ADDR": "192.168.0.1",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.2",
            },
            "http://spam/",
            id="ignore 0",
        ),
        pytest.param(
            {"x_for": 3},
            {
                "REMOTE_ADDR": "192.168.0.1",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.3, 192.168.0.2",
            },
            "http://spam/",
            id="ignore len < trusted",
        ),
        pytest.param(
            {},
            {
                "REMOTE_ADDR": "192.168.0.2",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.3, 192.168.0.1",
            },
            "http://spam/",
            id="ignore untrusted",
        ),
        pytest.param(
            {"x_for": 2},
            {
                "REMOTE_ADDR": "192.168.0.1",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": ", 192.168.0.3",
            },
            "http://spam/",
            id="ignore empty",
        ),
        pytest.param(
            {"x_for": 2, "x_prefix": 1},
            {
                "REMOTE_ADDR": "192.168.0.2",
                "HTTP_HOST": "spam",
                "HTTP_X_FORWARDED_FOR": "192.168.0.1, 192.168.0.3",
                "HTTP_X_FORWARDED_PREFIX": "/ham, /eggs",
            },
            "http://spam/eggs/",
            id="prefix < for",
        ),
    ),
)
def test_proxy_fix(kwargs, base, url_root):
    @Request.application
    def app(request):
        # for header
        assert request.remote_addr == "192.168.0.1"
        # proto, host, port, prefix headers
        assert request.url_root == url_root

        urls = url_map.bind_to_environ(request.environ)
        parrot_url = urls.build("parrot")
        # build includes prefix
        assert urls.build("parrot") == "/".join((request.script_root, "parrot"))
        # match doesn't include prefix
        assert urls.match("/parrot")[0] == "parrot"

        # location header will start with url_root
        return redirect(parrot_url)

    url_map = Map([Rule("/parrot", endpoint="parrot")])
    app = ProxyFix(app, **kwargs)

    base.setdefault("REMOTE_ADDR", "192.168.0.1")
    environ = create_environ(environ_overrides=base)

    # host is always added, remove it if the test doesn't set it
    if "HTTP_HOST" not in base:
        del environ["HTTP_HOST"]

    response = Client(app).open(Request(environ))
    assert response.location == f"{url_root}parrot"
