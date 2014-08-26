# -*- coding: utf-8 -*-
"""
    tests.serving
    ~~~~~~~~~~~~~

    Added serving tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import ssl

try:
    import httplib
except ImportError:
    from http import client as httplib
try:
    from urllib2 import urlopen, HTTPError
except ImportError:  # pragma: no cover
    from urllib.request import urlopen
    from urllib.error import HTTPError

try:
    import OpenSSL
except ImportError:
    OpenSSL = None


import pytest

from werkzeug import __version__ as version, serving
from werkzeug.testapp import test_app as _test_app
import threading


real_make_server = serving.make_server


@pytest.fixture
def dev_server(monkeypatch):
    def run_dev_server(application, *args, **kwargs):
        servers = []
        server_started = threading.Event()

        def tracking_make_server(*args, **kwargs):
            srv = real_make_server(*args, **kwargs)
            servers.append(srv)
            server_started.set()
            return srv
        monkeypatch.setattr(serving, 'make_server', tracking_make_server)

        def thread_func():
            serving.run_simple(
                *(('localhost', 0, application) + args),
                **kwargs
            )
        t = threading.Thread(target=thread_func)
        t.setDaemon(True)
        t.start()
        server_started.wait(5)
        if not servers:
            raise RuntimeError('Server startup timed out!')

        server = servers.pop()
        ip, port = server.socket.getsockname()[:2]
        if ':' in ip:
            ip = '[%s]' % ip
        return server, '%s:%d' % (ip, port)

    return run_dev_server


def test_serving(dev_server):
    server, addr = dev_server(_test_app)
    rv = urlopen('http://%s/?foo=bar&baz=blah' % addr).read()
    assert b'WSGI Information' in rv
    assert b'foo=bar&amp;baz=blah' in rv
    assert b'Werkzeug/' + version.encode('ascii') in rv


def test_broken_app(dev_server):
    def broken_app(environ, start_response):
        1 // 0
    server, addr = dev_server(broken_app)
    try:
        urlopen('http://%s/?foo=bar&baz=blah' % addr).read()
    except HTTPError as e:
        # In Python3 a 500 response causes an exception
        rv = e.read()
        assert b'Internal Server Error' in rv
    else:
        assert False, 'expected internal server error'


def test_absolute_requests(dev_server):
    def asserting_app(environ, start_response):
        assert environ['HTTP_HOST'] == 'surelynotexisting.example.com:1337'
        assert environ['PATH_INFO'] == '/index.htm'
        assert environ['SERVER_PORT'] == addr.split(':')[1]
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'YES']

    server, addr = dev_server(asserting_app)
    conn = httplib.HTTPConnection(addr)
    conn.request('GET', 'http://surelynotexisting.example.com:1337/index.htm')
    res = conn.getresponse()
    assert res.read() == b'YES'


@pytest.mark.skipif(not hasattr(ssl, 'SSLContext'),
                    reason='Missing PEP 466 (Python 2.7.9+) or Python 3.')
@pytest.mark.skipif(OpenSSL is None,
                    reason='OpenSSL is required for cert generation.')
def test_stdlib_ssl_contexts(dev_server, tmpdir):
    certificate, private_key = serving.make_ssl_devcert(str(tmpdir))
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(certificate, private_key)

    def hello(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    server, addr = dev_server(hello, ssl_context=ctx)
    assert addr is not None
    connection = httplib.HTTPSConnection(addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_ssl_context_adhoc(dev_server):
    def hello(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    server, addr = dev_server(hello, ssl_context='adhoc')
    assert addr is not None
    connection = httplib.HTTPSConnection(addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_make_ssl_devcert(tmpdir):
    certificate, private_key = \
        serving.make_ssl_devcert(str(tmpdir))
    assert os.path.isfile(certificate)
    assert os.path.isfile(private_key)
