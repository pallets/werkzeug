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
import textwrap
import time

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


def test_serving(dev_server):
    server = dev_server('from werkzeug.testapp import test_app as app')
    rv = urlopen('http://%s/?foo=bar&baz=blah' % server.addr).read()
    assert b'WSGI Information' in rv
    assert b'foo=bar&amp;baz=blah' in rv
    assert b'Werkzeug/' + version.encode('ascii') in rv


def test_broken_app(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        1 // 0
    ''')

    with pytest.raises(HTTPError) as excinfo:
        urlopen(server.url + '/?foo=bar&baz=blah').read()

    rv = excinfo.value.read()
    assert b'Internal Server Error' in rv


def test_absolute_requests(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        assert environ['HTTP_HOST'] == 'surelynotexisting.example.com:1337'
        assert environ['PATH_INFO'] == '/index.htm'
        addr = environ['HTTP_X_WERKZEUG_ADDR']
        assert environ['SERVER_PORT'] == addr.split(':')[1]
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'YES']
    ''')

    conn = httplib.HTTPConnection(server.addr)
    conn.request('GET', 'http://surelynotexisting.example.com:1337/index.htm#ignorethis',
                 headers={'X-Werkzeug-Addr': server.addr})
    res = conn.getresponse()
    assert res.read() == b'YES'


@pytest.mark.skipif(not hasattr(ssl, 'SSLContext'),
                    reason='Missing PEP 466 (Python 2.7.9+) or Python 3.')
@pytest.mark.skipif(OpenSSL is None,
                    reason='OpenSSL is required for cert generation.')
def test_stdlib_ssl_contexts(dev_server, tmpdir):
    certificate, private_key = \
        serving.make_ssl_devcert(str(tmpdir.mkdir('certs')))

    server = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']

    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain("%s", "%s")
    kwargs['ssl_context'] = ctx
    ''' % (certificate, private_key))

    assert server.addr is not None
    connection = httplib.HTTPSConnection(server.addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_ssl_context_adhoc(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']

    kwargs['ssl_context'] = 'adhoc'
    ''')
    connection = httplib.HTTPSConnection(server.addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_make_ssl_devcert(tmpdir):
    certificate, private_key = \
        serving.make_ssl_devcert(str(tmpdir))
    assert os.path.isfile(certificate)
    assert os.path.isfile(private_key)


@pytest.mark.parametrize('reloader_type', ['watchdog', 'stat'])
def test_reloader_broken_imports(tmpdir, dev_server, reloader_type):
    # We explicitly assert that the server reloads on change, even though in
    # this case the import could've just been retried. This is to assert
    # correct behavior for apps that catch and cache import errors.

    real_app = tmpdir.join('real_app.py')
    real_app.write("lol syntax error")

    server = dev_server('''
    trials = []
    def app(environ, start_response):
        assert not trials, 'should have reloaded'
        trials.append(1)
        import real_app
        return real_app.real_app(environ, start_response)

    kwargs['use_reloader'] = True
    kwargs['reloader_interval'] = 0.1
    kwargs['reloader_type'] = %s
    ''' % repr(reloader_type))
    server.wait_for_reloader_loop()

    connection = httplib.HTTPConnection(server.addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.status == 500

    real_app.write(textwrap.dedent('''
    def real_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    '''))
    server.wait_for_reloader()

    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.status == 200
    assert response.read() == b'hello'


@pytest.mark.parametrize('reloader_type', ['watchdog', 'stat'])
def test_reloader_nested_broken_imports(tmpdir, dev_server, reloader_type):
    real_app = tmpdir.mkdir('real_app')
    real_app.join('__init__.py').write('from real_app.sub import real_app')
    sub = real_app.mkdir('sub').join('__init__.py')
    sub.write("lol syntax error")

    server = dev_server('''
    trials = []
    def app(environ, start_response):
        assert not trials, 'should have reloaded'
        trials.append(1)
        import real_app
        return real_app.real_app(environ, start_response)

    kwargs['use_reloader'] = True
    kwargs['reloader_interval'] = 0.1
    kwargs['reloader_type'] = %s
    ''' % repr(reloader_type))
    server.wait_for_reloader_loop()

    connection = httplib.HTTPConnection(server.addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.status == 500

    sub.write(textwrap.dedent('''
    def real_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    '''))
    server.wait_for_reloader()

    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.status == 200
    assert response.read() == b'hello'
