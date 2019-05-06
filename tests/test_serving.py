# -*- coding: utf-8 -*-
"""
    tests.serving
    ~~~~~~~~~~~~~

    Added serving tests.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import os
import socket
import ssl
import subprocess
import sys
import textwrap
import time

import pytest
import requests.exceptions

from werkzeug import __version__ as version
from werkzeug import _reloader
from werkzeug import serving

try:
    import OpenSSL
except ImportError:
    OpenSSL = None

try:
    import watchdog
except ImportError:
    watchdog = None

try:
    from http import client as httplib
except ImportError:
    import httplib


def test_serving(dev_server):
    server = dev_server("from werkzeug.testapp import test_app as app")
    rv = requests.get("http://%s/?foo=bar&baz=blah" % server.addr).content
    assert b"WSGI Information" in rv
    assert b"foo=bar&amp;baz=blah" in rv
    assert b"Werkzeug/" + version.encode("ascii") in rv


def test_absolute_requests(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            assert environ['HTTP_HOST'] == 'surelynotexisting.example.com:1337'
            assert environ['PATH_INFO'] == '/index.htm'
            addr = environ['HTTP_X_WERKZEUG_ADDR']
            assert environ['SERVER_PORT'] == addr.split(':')[1]
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'YES']
        """
    )

    conn = httplib.HTTPConnection(server.addr)
    conn.request(
        "GET",
        "http://surelynotexisting.example.com:1337/index.htm#ignorethis",
        headers={"X-Werkzeug-Addr": server.addr},
    )
    res = conn.getresponse()
    assert res.read() == b"YES"


def test_double_slash_path(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            assert 'fail' not in environ['HTTP_HOST']
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'YES']
        """
    )

    r = requests.get(server.url + "//fail")
    assert r.content == b"YES"


def test_broken_app(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            1 // 0
        """
    )

    r = requests.get(server.url + "/?foo=bar&baz=blah")
    assert r.status_code == 500
    assert "Internal Server Error" in r.text


@pytest.mark.skipif(
    not hasattr(ssl, "SSLContext"),
    reason="Missing PEP 466 (Python 2.7.9+) or Python 3.",
)
@pytest.mark.skipif(OpenSSL is None, reason="OpenSSL is required for cert generation.")
def test_stdlib_ssl_contexts(dev_server, tmpdir):
    certificate, private_key = serving.make_ssl_devcert(str(tmpdir.mkdir("certs")))

    server = dev_server(
        """
        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'hello']

        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ctx.load_cert_chain(r"%s", r"%s")
        kwargs['ssl_context'] = ctx
        """
        % (certificate, private_key)
    )

    assert server.addr is not None
    r = requests.get(server.url, verify=False)
    assert r.content == b"hello"


@pytest.mark.skipif(OpenSSL is None, reason="OpenSSL is not installed.")
def test_ssl_context_adhoc(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'hello']

        kwargs['ssl_context'] = 'adhoc'
        """
    )
    r = requests.get(server.url, verify=False)
    assert r.content == b"hello"


@pytest.mark.skipif(OpenSSL is None, reason="OpenSSL is not installed.")
def test_make_ssl_devcert(tmpdir):
    certificate, private_key = serving.make_ssl_devcert(str(tmpdir))
    assert os.path.isfile(certificate)
    assert os.path.isfile(private_key)


@pytest.mark.skipif(watchdog is None, reason="Watchdog not installed.")
def test_reloader_broken_imports(tmpdir, dev_server):
    # We explicitly assert that the server reloads on change, even though in
    # this case the import could've just been retried. This is to assert
    # correct behavior for apps that catch and cache import errors.
    #
    # Because this feature is achieved by recursively watching a large amount
    # of directories, this only works for the watchdog reloader. The stat
    # reloader is too inefficient to watch such a large amount of files.

    real_app = tmpdir.join("real_app.py")
    real_app.write("lol syntax error")

    server = dev_server(
        """
        trials = []
        def app(environ, start_response):
            assert not trials, 'should have reloaded'
            trials.append(1)
            import real_app
            return real_app.real_app(environ, start_response)

        kwargs['use_reloader'] = True
        kwargs['reloader_interval'] = 0.1
        kwargs['reloader_type'] = 'watchdog'
        """
    )
    server.wait_for_reloader_loop()

    r = requests.get(server.url)
    assert r.status_code == 500

    real_app.write(
        textwrap.dedent(
            """
            def real_app(environ, start_response):
                start_response('200 OK', [('Content-Type', 'text/html')])
                return [b'hello']
            """
        )
    )
    server.wait_for_reloader()

    r = requests.get(server.url)
    assert r.status_code == 200
    assert r.content == b"hello"


@pytest.mark.skipif(watchdog is None, reason="Watchdog not installed.")
def test_reloader_nested_broken_imports(tmpdir, dev_server):
    real_app = tmpdir.mkdir("real_app")
    real_app.join("__init__.py").write("from real_app.sub import real_app")
    sub = real_app.mkdir("sub").join("__init__.py")
    sub.write("lol syntax error")

    server = dev_server(
        """
        trials = []
        def app(environ, start_response):
            assert not trials, 'should have reloaded'
            trials.append(1)
            import real_app
            return real_app.real_app(environ, start_response)

        kwargs['use_reloader'] = True
        kwargs['reloader_interval'] = 0.1
        kwargs['reloader_type'] = 'watchdog'
        """
    )
    server.wait_for_reloader_loop()

    r = requests.get(server.url)
    assert r.status_code == 500

    sub.write(
        textwrap.dedent(
            """
            def real_app(environ, start_response):
                start_response('200 OK', [('Content-Type', 'text/html')])
                return [b'hello']
            """
        )
    )
    server.wait_for_reloader()

    r = requests.get(server.url)
    assert r.status_code == 200
    assert r.content == b"hello"


@pytest.mark.skipif(watchdog is None, reason="Watchdog not installed.")
def test_reloader_reports_correct_file(tmpdir, dev_server):
    real_app = tmpdir.join("real_app.py")
    real_app.write(
        textwrap.dedent(
            """
            def real_app(environ, start_response):
                start_response('200 OK', [('Content-Type', 'text/html')])
                return [b'hello']
            """
        )
    )

    server = dev_server(
        """
        trials = []
        def app(environ, start_response):
            assert not trials, 'should have reloaded'
            trials.append(1)
            import real_app
            return real_app.real_app(environ, start_response)

        kwargs['use_reloader'] = True
        kwargs['reloader_interval'] = 0.1
        kwargs['reloader_type'] = 'watchdog'
        """
    )
    server.wait_for_reloader_loop()

    r = requests.get(server.url)
    assert r.status_code == 200
    assert r.content == b"hello"

    real_app_binary = tmpdir.join("real_app.pyc")
    real_app_binary.write("anything is fine here")
    server.wait_for_reloader()

    change_event = " * Detected change in '%(path)s', reloading" % {
        # need to double escape Windows paths
        "path": str(real_app_binary).replace("\\", "\\\\")
    }
    server.logfile.seek(0)
    for i in range(20):
        time.sleep(0.1 * i)
        log = server.logfile.read()
        if change_event in log:
            break
    else:
        raise RuntimeError("Change event not detected.")


def test_windows_get_args_for_reloading(monkeypatch, tmpdir):
    test_py_exe = r"C:\Users\test\AppData\Local\Programs\Python\Python36\python.exe"
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(sys, "executable", test_py_exe)
    test_exe = tmpdir.mkdir("test").join("test.exe")
    monkeypatch.setattr(sys, "argv", [test_exe.strpath, "run"])
    rv = _reloader._get_args_for_reloading()
    assert rv == [test_exe.strpath, "run"]


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


def test_wrong_protocol(dev_server):
    # Assert that sending HTTPS requests to a HTTP server doesn't show a
    # traceback
    # See https://github.com/pallets/werkzeug/pull/838

    server = dev_server(
        """
        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'hello']
        """
    )
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://%s/" % server.addr)

    log = server.logfile.read()
    assert "Traceback" not in log
    assert "\n127.0.0.1" in log


def test_absent_content_length_and_content_type(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            assert 'CONTENT_LENGTH' not in environ
            assert 'CONTENT_TYPE' not in environ
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'YES']
        """
    )

    r = requests.get(server.url)
    assert r.content == b"YES"


def test_set_content_length_and_content_type_if_provided_by_client(dev_server):
    server = dev_server(
        """
        def app(environ, start_response):
            assert environ['CONTENT_LENGTH'] == '233'
            assert environ['CONTENT_TYPE'] == 'application/json'
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [b'YES']
        """
    )

    r = requests.get(
        server.url,
        headers={"content_length": "233", "content_type": "application/json"},
    )
    assert r.content == b"YES"


def test_port_must_be_integer(dev_server):
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


def test_chunked_encoding(dev_server):
    server = dev_server(
        r"""
        from werkzeug.wrappers import Request
        def app(environ, start_response):
            assert environ['HTTP_TRANSFER_ENCODING'] == 'chunked'
            assert environ.get('wsgi.input_terminated', False)
            request = Request(environ)
            assert request.mimetype == 'multipart/form-data'
            assert request.files['file'].read() == b'This is a test\n'
            assert request.form['type'] == 'text/plain'
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'YES']
        """
    )

    testfile = os.path.join(os.path.dirname(__file__), "res", "chunked.http")

    conn = httplib.HTTPConnection("127.0.0.1", server.port)
    conn.connect()
    conn.putrequest("POST", "/", skip_host=1, skip_accept_encoding=1)
    conn.putheader("Accept", "text/plain")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.putheader(
        "Content-Type",
        "multipart/form-data; boundary="
        "--------------------------898239224156930639461866",
    )
    conn.endheaders()

    with open(testfile, "rb") as f:
        conn.send(f.read())

    res = conn.getresponse()
    assert res.status == 200
    assert res.read() == b"YES"

    conn.close()


def test_chunked_encoding_with_content_length(dev_server):
    server = dev_server(
        r"""
        from werkzeug.wrappers import Request
        def app(environ, start_response):
            assert environ['HTTP_TRANSFER_ENCODING'] == 'chunked'
            assert environ.get('wsgi.input_terminated', False)
            request = Request(environ)
            assert request.mimetype == 'multipart/form-data'
            assert request.files['file'].read() == b'This is a test\n'
            assert request.form['type'] == 'text/plain'
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'YES']
        """
    )

    testfile = os.path.join(os.path.dirname(__file__), "res", "chunked.http")

    conn = httplib.HTTPConnection("127.0.0.1", server.port)
    conn.connect()
    conn.putrequest("POST", "/", skip_host=1, skip_accept_encoding=1)
    conn.putheader("Accept", "text/plain")
    conn.putheader("Transfer-Encoding", "chunked")
    # Content-Length is invalid for chunked, but some libraries might send it
    conn.putheader("Content-Length", "372")
    conn.putheader(
        "Content-Type",
        "multipart/form-data; boundary="
        "--------------------------898239224156930639461866",
    )
    conn.endheaders()

    with open(testfile, "rb") as f:
        conn.send(f.read())

    res = conn.getresponse()
    assert res.status == 200
    assert res.read() == b"YES"

    conn.close()


def test_multiple_headers_concatenated_per_rfc_3875_section_4_1_18(dev_server):
    server = dev_server(
        r"""
        from werkzeug.wrappers import Response
        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [environ['HTTP_XYZ'].encode()]
        """
    )

    conn = httplib.HTTPConnection("127.0.0.1", server.port)
    conn.connect()
    conn.putrequest("GET", "/")
    conn.putheader("Accept", "text/plain")
    conn.putheader("XYZ", " a ")
    conn.putheader("X-INGNORE-1", "Some nonsense")
    conn.putheader("XYZ", " b")
    conn.putheader("X-INGNORE-2", "Some nonsense")
    conn.putheader("XYZ", "c ")
    conn.putheader("X-INGNORE-3", "Some nonsense")
    conn.putheader("XYZ", "d")
    conn.endheaders()
    conn.send(b"")
    res = conn.getresponse()

    assert res.status == 200
    assert res.read() == b"a ,b,c ,d"

    conn.close()


def test_multiline_header_folding_for_http_1_1(dev_server):
    """
    This is testing the provision of multi-line header folding per:
     * RFC 2616 Section 2.2
     * RFC 3875 Section 4.1.18
    """
    server = dev_server(
        r"""
        from werkzeug.wrappers import Response
        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [environ['HTTP_XYZ'].encode()]
        """
    )

    conn = httplib.HTTPConnection("127.0.0.1", server.port)
    conn.connect()
    conn.putrequest("GET", "/")
    conn.putheader("Accept", "text/plain")
    conn.putheader("XYZ", "first-line", "second-line", "third-line")
    conn.endheaders()
    conn.send(b"")
    res = conn.getresponse()

    assert res.status == 200
    assert res.read() == b"first-line\tsecond-line\tthird-line"

    conn.close()


def can_test_unix_socket():
    if not hasattr(socket, "AF_UNIX"):
        return False
    try:
        import requests_unixsocket  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not can_test_unix_socket(), reason="Only works on UNIX")
def test_unix_socket(tmpdir, dev_server):
    socket_f = str(tmpdir.join("socket"))
    dev_server(
        """
        app = None
        kwargs['hostname'] = {socket!r}
        """.format(
            socket="unix://" + socket_f
        )
    )
    assert os.path.exists(socket_f)
