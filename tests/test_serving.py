import inspect
import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import textwrap
import time
from http import client as http_client

import pytest
import test_apps.reloader_real_app as reloader_real_app

from werkzeug import __version__ as version
from werkzeug import _reloader
from werkzeug import serving


try:
    import cryptography
except ImportError:
    cryptography = None

try:
    import watchdog
except ImportError:
    watchdog = None


require_cryptography = pytest.mark.skipif(
    cryptography is None, reason="cryptography not installed"
)
require_watchdog = pytest.mark.skipif(watchdog is None, reason="watchdog not installed")
skip_windows = pytest.mark.skipif(
    platform.system() == "Windows", reason="unreliable on Windows"
)


def test_serving(dev_server):
    server = dev_server("test_app")
    r = server.get(f"http://{server.addr}/?foo=bar&baz=blah").read().decode()
    assert "WSGI Information" in r
    assert "foo=bar&amp;baz=blah" in r
    assert f"Werkzeug/{version}" in r


def test_absolute_requests(standard_app):
    r = standard_app.get(
        "http://surelynotexisting.example.com:1337/index.htm#ignorethis",
        headers={"X-Werkzeug-Addr": standard_app.addr},
    )
    environ = json.loads(r.read())

    assert environ["HTTP_HOST"] == "surelynotexisting.example.com:1337"
    assert environ["PATH_INFO"] == "/index.htm"
    addr = environ["HTTP_X_WERKZEUG_ADDR"]
    assert environ["SERVER_PORT"] == addr.split(":")[1]


def test_double_slash_path(standard_app):
    r = standard_app.get(f"{standard_app.url}//fail")
    environ = json.loads(r.read())

    assert "fail" not in environ["HTTP_HOST"]


def test_broken_app(standard_app):
    r = standard_app.get(f"{standard_app.url}/crash=True")

    assert r.status == 500
    assert b"Internal Server Error" in r.read()


@require_cryptography
def test_stdlib_ssl_contexts(dev_server, monkeypatch):
    monkeypatch.setattr(
        ssl, "_create_default_https_context", ssl._create_unverified_context
    )
    server = dev_server("stdlib_ssl_app", ssl_context="to be generated")

    assert server.addr is not None
    r = server.get(server.url)

    assert r.status == 200
    assert r.read() == b"hello"


@require_cryptography
def test_ssl_context_adhoc(dev_server, monkeypatch):
    monkeypatch.setattr(
        ssl, "_create_default_https_context", ssl._create_unverified_context
    )
    server = dev_server("standard_app", ssl_context="adhoc")
    r = server.get(server.url)

    assert r.status == 200


@require_cryptography
def test_make_ssl_devcert(tmpdir):
    certificate, private_key = serving.make_ssl_devcert(str(tmpdir))
    assert os.path.isfile(certificate)
    assert os.path.isfile(private_key)


@require_watchdog
@skip_windows
def test_reloader_broken_imports(tmpdir_factory, dev_server):
    # We explicitly assert that the server reloads on change, even though in
    # this case the import could've just been retried. This is to assert
    # correct behavior for apps that catch and cache import errors.
    #
    # Because this feature is achieved by recursively watching a large amount
    # of directories, this only works for the watchdog reloader. The stat
    # reloader is too inefficient to watch such a large amount of files.

    real_app = tmpdir_factory.getbasetemp().join("real_app.py")
    real_app.write("lol syntax error")

    server = dev_server(
        "reloader_app",
        use_reloader=True,
        reloader_interval=0.1,
        reloader_type="watchdog",
    )
    server.wait_for_reloader_loop()

    r = server.get(server.url)
    assert r.status == 500

    real_app.write(inspect.getsource(reloader_real_app))
    server.wait_for_reloader()

    r = server.get(server.url)
    assert r.status == 200
    assert r.read() == b"hello"


@require_watchdog
@skip_windows
def test_reloader_nested_broken_imports(tmpdir_factory, dev_server):
    real_app = tmpdir_factory.getbasetemp().mkdir("real_app")
    real_app.join("__init__.py").write("from real_app.sub import real_app")
    sub = real_app.mkdir("sub").join("__init__.py")
    sub.write("lol syntax error")

    server = dev_server(
        "reloader_app",
        use_reloader=True,
        reloader_interval=0.1,
        reloader_type="watchdog",
    )
    server.wait_for_reloader_loop()

    r = server.get(server.url)
    assert r.status == 500

    sub.write(inspect.getsource(reloader_real_app))
    server.wait_for_reloader()

    r = server.get(server.url)
    assert r.status == 200
    assert r.read() == b"hello"


@require_watchdog
@skip_windows
def test_reloader_reports_correct_file(tmpdir_factory, dev_server):
    real_app = tmpdir_factory.getbasetemp().join("real_app.py")
    real_app.write(inspect.getsource(reloader_real_app))

    server = dev_server(
        "reloader_app",
        use_reloader=True,
        reloader_interval=0.1,
        reloader_type="watchdog",
    )
    server.wait_for_reloader_loop()

    r = server.get(server.url)
    assert r.status == 200
    assert r.read() == b"hello"

    real_app_binary = tmpdir_factory.getbasetemp().join("real_app.pyc")
    real_app_binary.write("anything is fine here")
    server.wait_for_reloader()

    escaped_path = str(real_app_binary).replace("\\", "\\\\")
    change_event = f" * Detected change in {escaped_path!r}, reloading"
    server.logfile.seek(0)
    for i in range(20):
        time.sleep(0.1 * i)
        log = server.logfile.read()
        if change_event in log:
            break
    else:
        raise RuntimeError("Change event not detected.")


def test_windows_get_args_for_reloading(monkeypatch, tmp_path):
    argv = [str(tmp_path / "test.exe"), "run"]
    monkeypatch.setattr("sys.executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr("sys.argv", argv)
    monkeypatch.setattr("__main__.__package__", None)
    monkeypatch.setattr("os.name", "nt")
    rv = _reloader._get_args_for_reloading()
    assert rv == argv


def test_monkeypatched_sleep(tmpdir):
    # removing the staticmethod wrapper in the definition of
    # ReloaderLoop._sleep works most of the time, since `sleep` is a c
    # function, and unlike python functions which are descriptors, doesn't
    # become a method when attached to a class. however, if the user has called
    # `eventlet.monkey_patch` before importing `_reloader`, `time.sleep` is a
    # python function, and subsequently calling `ReloaderLoop._sleep` fails
    # with a TypeError. This test checks that _sleep is attached correctly.
    script = tmpdir.mkdir("app").join("test.py")
    script.write(
        textwrap.dedent(
            """
            import time

            def sleep(secs):
                pass

            # simulate eventlet.monkey_patch by replacing the builtin sleep
            # with a regular function before _reloader is imported
            time.sleep = sleep

            from werkzeug._reloader import ReloaderLoop
            ReloaderLoop()._sleep(0)
            """
        )
    )
    subprocess.check_call([sys.executable, str(script)])


def test_wrong_protocol(standard_app):
    # Assert that sending HTTPS requests to a HTTP server doesn't show a
    # traceback
    # See https://github.com/pallets/werkzeug/pull/838

    with pytest.raises(ssl.SSLError):
        conn = http_client.HTTPSConnection(standard_app.addr)
        conn.request("GET", f"https://{standard_app.addr}")

    log = standard_app.logfile.readlines()[-2]
    assert "Traceback" not in log
    assert "127.0.0.1" in log


def test_absent_content_length_and_content_type(standard_app):
    r = standard_app.get(standard_app.url)
    environ = json.loads(r.read())

    assert "CONTENT_LENGTH" not in environ
    assert "CONTENT_TYPE" not in environ


def test_set_content_length_and_content_type_if_provided_by_client(standard_app):
    r = standard_app.get(
        f"{standard_app.url}",
        headers={"content_length": "233", "content_type": "application/json"},
    )
    environ = json.loads(r.read())

    assert environ["CONTENT_LENGTH"] == "233"
    assert environ["CONTENT_TYPE"] == "application/json"


def test_port_must_be_integer():
    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/html")])
        return [b"hello"]

    with pytest.raises(TypeError) as excinfo:
        serving.run_simple(
            hostname="localhost", port="5001", application=app, use_reloader=True
        )
    assert "port must be an integer" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        serving.run_simple(
            hostname="localhost", port="5001", application=app, use_reloader=False
        )
    assert "port must be an integer" in str(excinfo.value)


def test_chunked_encoding(chunked_app):
    testfile = os.path.join(os.path.dirname(__file__), "res", "chunked.http")

    chunked_app.conn.putrequest("POST", "/", skip_host=1, skip_accept_encoding=1)
    chunked_app.conn.putheader("Accept", "text/plain")
    chunked_app.conn.putheader("Transfer-Encoding", "chunked")
    chunked_app.conn.putheader(
        "Content-Type",
        "multipart/form-data; boundary="
        "--------------------------898239224156930639461866",
    )
    chunked_app.conn.endheaders()

    with open(testfile, "rb") as f:
        chunked_app.conn.send(f.read())

    res = chunked_app.conn.getresponse()
    assert res.status == 200
    assert res.read() == b"YES"


def test_chunked_encoding_with_content_length(chunked_app):
    testfile = os.path.join(os.path.dirname(__file__), "res", "chunked.http")

    chunked_app.conn.putrequest("POST", "/", skip_host=1, skip_accept_encoding=1)
    chunked_app.conn.putheader("Accept", "text/plain")
    chunked_app.conn.putheader("Transfer-Encoding", "chunked")
    # Content-Length is invalid for chunked, but some libraries might send it
    chunked_app.conn.putheader("Content-Length", "372")
    chunked_app.conn.putheader(
        "Content-Type",
        "multipart/form-data; boundary="
        "--------------------------898239224156930639461866",
    )
    chunked_app.conn.endheaders()

    with open(testfile, "rb") as f:
        chunked_app.conn.send(f.read())

    res = chunked_app.conn.getresponse()
    assert res.status == 200
    assert res.read() == b"YES"


def test_multiple_headers_concatenated_per_rfc_3875_section_4_1_18(standard_app):
    standard_app.conn.putrequest("GET", "/")
    standard_app.conn.putheader("Accept", "text/plain")
    standard_app.conn.putheader("XYZ", " a ")
    standard_app.conn.putheader("X-INGNORE-1", "Some nonsense")
    standard_app.conn.putheader("XYZ", " b")
    standard_app.conn.putheader("X-INGNORE-2", "Some nonsense")
    standard_app.conn.putheader("XYZ", "c ")
    standard_app.conn.putheader("X-INGNORE-3", "Some nonsense")
    standard_app.conn.putheader("XYZ", "d")
    standard_app.conn.endheaders()
    standard_app.conn.send(b"")
    res = standard_app.conn.getresponse()

    assert res.status == 200
    environ = json.loads(res.read())
    assert environ["HTTP_XYZ"].encode() == b"a ,b,c ,d"


def test_multiline_header_folding_for_http_1_1(standard_app):
    """
    This is testing the provision of multi-line header folding per:
     * RFC 2616 Section 2.2
     * RFC 3875 Section 4.1.18
    """
    standard_app.conn.putrequest("GET", "/")
    standard_app.conn.putheader("Accept", "text/plain")
    standard_app.conn.putheader("XYZ", "first-line", "second-line", "third-line")
    standard_app.conn.endheaders()
    standard_app.conn.send(b"")
    res = standard_app.conn.getresponse()

    assert res.status == 200
    environ = json.loads(res.read())
    assert environ["HTTP_XYZ"].encode() == b"first-line\tsecond-line\tthird-line"


def can_test_unix_socket():
    if not hasattr(socket, "AF_UNIX"):
        return False
    return True


@pytest.mark.skipif(not can_test_unix_socket(), reason="Only works on UNIX")
def test_unix_socket(tmpdir, dev_server):
    socket_f = str(tmpdir.join("socket"))
    dev_server(None, hostname=f"unix://{socket_f}")
    assert os.path.exists(socket_f)
