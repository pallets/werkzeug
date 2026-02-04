from __future__ import annotations

import collections.abc as cabc
import http.client
import importlib.metadata
import json
import os
import shutil
import socket
import ssl
import typing as t
from importlib.metadata import PackageNotFoundError
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from werkzeug import run_simple
from werkzeug._reloader import _find_stat_paths
from werkzeug._reloader import _find_watchdog_paths
from werkzeug._reloader import WatchdogReloaderLoop
from werkzeug.datastructures import FileStorage
from werkzeug.serving import make_ssl_devcert
from werkzeug.test import stream_encode_multipart

if t.TYPE_CHECKING:
    from conftest import DevServerClient
    from conftest import StartDevServer

try:
    watchdog_version: str = importlib.metadata.version("watchdog")
except PackageNotFoundError:
    watchdog_version = ""


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="http"),
        pytest.param({"ssl_context": "adhoc"}, id="https"),
        pytest.param({"use_reloader": True}, id="reloader"),
        pytest.param(
            {"hostname": "unix"},
            id="unix socket",
            marks=pytest.mark.skipif(
                not hasattr(socket, "AF_UNIX"), reason="requires unix socket support"
            ),
        ),
    ],
)
@pytest.mark.dev_server
def test_server(
    tmp_path_factory: pytest.TempPathFactory,
    dev_server: StartDevServer,
    kwargs: dict[str, t.Any],
) -> None:
    if kwargs.get("hostname") == "unix":
        # Pytest's tmp_path is too long on macOS, use a shorter name.
        tmp_path = tmp_path_factory.mktemp("sock")
        kwargs["hostname"] = f"unix://{tmp_path / 'test.sock'}"

    client = dev_server(**kwargs)
    r = client.request()
    assert r.status == 200
    assert r.json["PATH_INFO"] == "/"


@pytest.mark.dev_server
def test_untrusted_host(standard_app: DevServerClient) -> None:
    r = standard_app.request(
        "http://missing.test:1337/index.html#ignore",
        headers={"x-base-url": standard_app.url},
    )
    assert r.json["HTTP_HOST"] == "missing.test:1337"
    assert r.json["PATH_INFO"] == "/index.html"
    host, _, port = r.json["HTTP_X_BASE_URL"].rpartition(":")
    assert r.json["SERVER_NAME"] == host.partition("http://")[2]
    assert r.json["SERVER_PORT"] == port


@pytest.mark.dev_server
def test_double_slash_path(standard_app: DevServerClient) -> None:
    r = standard_app.request("//double-slash")
    assert "double-slash" not in r.json["HTTP_HOST"]
    assert r.json["PATH_INFO"] == "/double-slash"


@pytest.mark.dev_server
def test_500_error(standard_app: DevServerClient) -> None:
    r = standard_app.request("/crash")
    assert r.status == 500
    assert b"Internal Server Error" in r.data


@pytest.mark.dev_server
def test_ssl_dev_cert(tmp_path: Path, dev_server: StartDevServer) -> None:
    client = dev_server(ssl_context=make_ssl_devcert(os.fspath(tmp_path)))
    r = client.request()
    assert r.json["wsgi.url_scheme"] == "https"


@pytest.mark.dev_server
def test_ssl_object(dev_server: StartDevServer) -> None:
    client = dev_server(ssl_context="custom")
    r = client.request()
    assert r.json["wsgi.url_scheme"] == "https"


require_watchdog = pytest.mark.skipif(
    not watchdog_version, reason="watchdog not installed"
)


@pytest.mark.parametrize(
    "reloader_type", ["stat", pytest.param("watchdog", marks=[require_watchdog])]
)
@pytest.mark.skipif(
    os.name == "nt" and "CI" in os.environ, reason="unreliable on Windows during CI"
)
@pytest.mark.dev_server
def test_reloader_sys_path(
    tmp_path: Path, dev_server: StartDevServer, reloader_type: str
) -> None:
    """This tests the general behavior of the reloader. It also tests
    that fixing an import error triggers a reload, not just Python
    retrying the failed import.
    """
    real_path = tmp_path / "real_app.py"
    real_path.write_text("syntax error causes import error")

    client = dev_server("reloader", reloader_type=reloader_type)
    assert client.request().status == 500

    shutil.copyfile(Path(__file__).parent / "live_apps" / "standard_app.py", real_path)
    client.wait_for_log(f"Detected change in {str(real_path)!r}")
    client.wait_for_reload()
    assert client.request().status == 200


@require_watchdog
@patch.object(WatchdogReloaderLoop, "trigger_reload")
def test_watchdog_reloader_ignores_opened(mock_trigger_reload: Mock) -> None:
    from watchdog.events import EVENT_TYPE_MODIFIED
    from watchdog.events import EVENT_TYPE_OPENED
    from watchdog.events import FileModifiedEvent

    reloader = WatchdogReloaderLoop()
    modified_event = FileModifiedEvent("fake.py")
    modified_event.event_type = EVENT_TYPE_MODIFIED
    reloader.event_handler.dispatch(modified_event)
    mock_trigger_reload.assert_called_once()

    mock_trigger_reload.reset_mock()
    opened_event = FileModifiedEvent("fake.py")
    opened_event.event_type = EVENT_TYPE_OPENED
    reloader.event_handler.dispatch(opened_event)
    mock_trigger_reload.assert_not_called()


@pytest.mark.skipif(
    watchdog_version < "5",
    reason="'closed no write' event introduced in watchdog 5.0",
)
@patch.object(WatchdogReloaderLoop, "trigger_reload")
def test_watchdog_reloader_ignores_closed_no_write(mock_trigger_reload: Mock) -> None:
    from watchdog.events import EVENT_TYPE_CLOSED_NO_WRITE
    from watchdog.events import EVENT_TYPE_MODIFIED
    from watchdog.events import FileModifiedEvent

    reloader = WatchdogReloaderLoop()
    modified_event = FileModifiedEvent("fake.py")
    modified_event.event_type = EVENT_TYPE_MODIFIED
    reloader.event_handler.dispatch(modified_event)
    mock_trigger_reload.assert_called_once()

    mock_trigger_reload.reset_mock()
    opened_event = FileModifiedEvent("fake.py")
    opened_event.event_type = EVENT_TYPE_CLOSED_NO_WRITE
    reloader.event_handler.dispatch(opened_event)
    mock_trigger_reload.assert_not_called()


@pytest.mark.parametrize("find", [_find_stat_paths, _find_watchdog_paths])
def test_exclude_patterns(
    find: t.Callable[[set[str], set[str]], cabc.Iterable[str]],
) -> None:
    # Select a path to exclude from the unfiltered list, assert that it is present and
    # then gets excluded.
    paths = find(set(), set())
    path_to_exclude = next(iter(paths))
    assert any(p.startswith(path_to_exclude) for p in paths)

    # Those paths should be excluded due to the pattern.
    paths = find(set(), {f"{path_to_exclude}*"})
    assert not any(p.startswith(path_to_exclude) for p in paths)


@pytest.mark.dev_server
def test_wrong_protocol(standard_app: DevServerClient) -> None:
    """An HTTPS request to an HTTP server doesn't show a traceback.
    https://github.com/pallets/werkzeug/pull/838
    """
    conn = http.client.HTTPSConnection(standard_app.addr)

    with pytest.raises(ssl.SSLError):
        conn.request("GET", f"https://{standard_app.addr}")

    assert "Traceback" not in standard_app.read_log()


@pytest.mark.dev_server
def test_content_type_and_length(standard_app: DevServerClient) -> None:
    r = standard_app.request()
    assert "CONTENT_TYPE" not in r.json
    assert "CONTENT_LENGTH" not in r.json

    r = standard_app.request(body=b"{}", headers={"content-type": "application/json"})
    assert r.json["CONTENT_TYPE"] == "application/json"
    assert r.json["CONTENT_LENGTH"] == "2"


def test_port_is_int() -> None:
    with pytest.raises(TypeError, match="port must be an integer"):
        run_simple("127.0.0.1", "5000", None)  # type: ignore[arg-type]


@pytest.mark.parametrize("send_length", [False, True])
@pytest.mark.dev_server
def test_chunked_request(
    monkeypatch: pytest.MonkeyPatch, dev_server: StartDevServer, send_length: bool
) -> None:
    stream, length, boundary = stream_encode_multipart(
        {
            "value": "this is text",
            "file": FileStorage(
                BytesIO(b"this is a file"),
                filename="test.txt",
                content_type="text/plain",
            ),
        }
    )
    client = dev_server("data")
    # Small block size to produce multiple chunks.
    conn = client.connect(blocksize=128)
    conn.putrequest("POST", "/")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")

    # Sending the content-length header with chunked is invalid, but if
    # a client does send it the server should ignore it. Previously the
    # multipart parser would crash. Python's higher-level functions
    # won't send the header, which is why we use conn.put in this test.
    if send_length:
        conn.putheader("Content-Length", "invalid")
        expect_content_len = "invalid"
    else:
        expect_content_len = None

    conn.endheaders(stream, encode_chunked=True)
    r = conn.getresponse()
    data = json.load(r)
    r.close()
    assert data["form"]["value"] == "this is text"
    assert data["files"]["file"] == "this is a file"
    environ = data["environ"]
    assert environ["HTTP_TRANSFER_ENCODING"] == "chunked"
    assert environ.get("CONTENT_LENGTH") == expect_content_len
    assert environ["wsgi.input_terminated"]


@pytest.mark.dev_server
def test_multiple_headers_concatenated(standard_app: DevServerClient) -> None:
    """A header key can be sent multiple times. The server will join all
    the values with commas.

    https://tools.ietf.org/html/rfc3875#section-4.1.18
    """
    # conn.request doesn't support multiple values.
    conn = standard_app.connect()
    conn.putrequest("GET", "/")
    conn.putheader("XYZ", "a ")  # trailing space is preserved
    conn.putheader("X-Ignore-1", "ignore value")
    conn.putheader("XYZ", " b")  # leading space is collapsed
    conn.putheader("X-Ignore-2", "ignore value")
    conn.putheader("XYZ", "c ")
    conn.putheader("X-Ignore-3", "ignore value")
    conn.putheader("XYZ", "d")
    conn.endheaders()
    r = conn.getresponse()
    data = json.load(r)
    r.close()
    assert data["HTTP_XYZ"] == "a ,b,c ,d"


@pytest.mark.dev_server
def test_multiline_header_folding(standard_app: DevServerClient) -> None:
    """A header value can be split over multiple lines with a leading
    tab. The server will remove the newlines and preserve the tabs.

    https://tools.ietf.org/html/rfc2616#section-2.2
    """
    # conn.request doesn't support multiline values.
    conn = standard_app.connect()
    conn.putrequest("GET", "/")
    conn.putheader("XYZ", "first", "second", "third")
    conn.endheaders()
    r = conn.getresponse()
    data = json.load(r)
    r.close()
    assert data["HTTP_XYZ"] == "first\tsecond\tthird"


@pytest.mark.parametrize("endpoint", ["", "crash"])
@pytest.mark.dev_server
def test_streaming_close_response(dev_server: StartDevServer, endpoint: str) -> None:
    """When using HTTP/1.0, chunked encoding is not supported. Fall
    back to Connection: close, but this allows no reliable way to
    distinguish between complete and truncated responses.
    """
    r = dev_server("streaming").request("/" + endpoint)
    assert r.getheader("connection") == "close"
    assert r.data == "".join(str(x) + "\n" for x in range(5)).encode()


@pytest.mark.dev_server
def test_streaming_chunked_response(dev_server: StartDevServer) -> None:
    """When using HTTP/1.1, use Transfer-Encoding: chunked for streamed
    responses, since it can distinguish the end of the response without
    closing the connection.

    https://tools.ietf.org/html/rfc2616#section-3.6.1
    """
    r = dev_server("streaming", threaded=True).request("/")
    assert r.getheader("transfer-encoding") == "chunked"
    assert r.data == "".join(str(x) + "\n" for x in range(5)).encode()


@pytest.mark.dev_server
def test_streaming_chunked_truncation(dev_server: StartDevServer) -> None:
    """When using HTTP/1.1, chunked encoding allows the client to detect
    content truncated by a prematurely closed connection.
    """
    with pytest.raises(http.client.IncompleteRead):
        dev_server("streaming", threaded=True).request("/crash")


@pytest.mark.dev_server
def test_host_with_ipv6_scope(dev_server: StartDevServer) -> None:
    client = dev_server(override_client_addr="fe80::1ff:fe23:4567:890a%eth2")
    r = client.request("/crash")

    assert r.status == 500
    assert b"Internal Server Error" in r.data
    assert "Logging error" not in client.read_log()
