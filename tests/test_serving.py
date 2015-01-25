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


try:
    import OpenSSL
except ImportError:
    OpenSSL = None

try:
    import watchdog
except ImportError:
    watchdog = None

import requests
import requests.exceptions
import pytest

from werkzeug import __version__ as version, serving


def test_serving(dev_server):
    server = dev_server('from werkzeug.testapp import test_app as app')
    rv = requests.get('http://%s/?foo=bar&baz=blah' % server.addr).content
    assert b'WSGI Information' in rv
    assert b'foo=bar&amp;baz=blah' in rv
    assert b'Werkzeug/' + version.encode('ascii') in rv


def test_broken_app(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        1 // 0
    ''')

    r = requests.get(server.url + '/?foo=bar&baz=blah')
    assert r.status_code == 500
    assert 'Internal Server Error' in r.text


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
    r = requests.get(server.url, verify=False)
    assert r.content == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_ssl_context_adhoc(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']

    kwargs['ssl_context'] = 'adhoc'
    ''')
    r = requests.get(server.url, verify=False)
    assert r.content == b'hello'


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
    if reloader_type == 'watchdog' and watchdog is None:
        pytest.skip('Watchdog not installed.')

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

    r = requests.get(server.url)
    assert r.status_code == 500

    real_app.write(textwrap.dedent('''
    def real_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    '''))
    server.wait_for_reloader()

    r = requests.get(server.url)
    assert r.status_code == 200
    assert r.content == b'hello'


@pytest.mark.parametrize('reloader_type', ['watchdog', 'stat'])
def test_reloader_nested_broken_imports(tmpdir, dev_server, reloader_type):
    if reloader_type == 'watchdog' and watchdog is None:
        pytest.skip('Watchdog not installed.')

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

    r = requests.get(server.url)
    assert r.status_code == 500

    sub.write(textwrap.dedent('''
    def real_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    '''))
    server.wait_for_reloader()

    r = requests.get(server.url)
    assert r.status_code == 200
    assert r.content == b'hello'
