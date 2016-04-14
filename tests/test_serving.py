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
import subprocess
import textwrap


try:
    import OpenSSL
except ImportError:
    OpenSSL = None

try:
    import watchdog
except ImportError:
    watchdog = None

try:
    import httplib
except ImportError:
    from http import client as httplib

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


def test_double_slash_path(dev_server):
    server = dev_server('''
    def app(environ, start_response):
        assert 'fail' not in environ['HTTP_HOST']
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'YES']
    ''')

    r = requests.get(server.url + '//fail')
    assert r.content == b'YES'


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


@pytest.mark.skipif(watchdog is None, reason='Watchdog not installed.')
def test_reloader_broken_imports(tmpdir, dev_server):
    # We explicitly assert that the server reloads on change, even though in
    # this case the import could've just been retried. This is to assert
    # correct behavior for apps that catch and cache import errors.
    #
    # Because this feature is achieved by recursively watching a large amount
    # of directories, this only works for the watchdog reloader. The stat
    # reloader is too inefficient to watch such a large amount of files.

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
    kwargs['reloader_type'] = 'watchdog'
    ''')
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


@pytest.mark.skipif(watchdog is None, reason='Watchdog not installed.')
def test_reloader_nested_broken_imports(tmpdir, dev_server):
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
    kwargs['reloader_type'] = 'watchdog'
    ''')
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


def test_monkeypached_sleep(tmpdir):
    # removing the staticmethod wrapper in the definition of
    # ReloaderLoop._sleep works most of the time, since `sleep` is a c
    # function, and unlike python functions which are descriptors, doesn't
    # become a method when attached to a class. however, if the user has called
    # `eventlet.monkey_patch` before importing `_reloader`, `time.sleep` is a
    # python function, and subsequently calling `ReloaderLoop._sleep` fails
    # with a TypeError. This test checks that _sleep is attached correctly.
    script = tmpdir.mkdir('app').join('test.py')
    script.write(textwrap.dedent('''
    import time

    def sleep(secs):
        pass

    # simulate eventlet.monkey_patch by replacing the builtin sleep
    # with a regular function before _reloader is imported
    time.sleep = sleep

    from werkzeug._reloader import ReloaderLoop
    ReloaderLoop()._sleep(0)
    '''))
    subprocess.check_call(['python', str(script)])


def test_wrong_protocol(dev_server):
    # Assert that sending HTTPS requests to a HTTP server doesn't show a
    # traceback
    # See https://github.com/mitsuhiko/werkzeug/pull/838

    server = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    ''')
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get('https://%s/' % server.addr)

    log = server.logfile.read()
    assert 'Traceback' not in log
    assert '\n127.0.0.1' in log
