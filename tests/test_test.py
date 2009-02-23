# -*- coding: utf-8 -*-
"""
    werkzeug.test test
    ~~~~~~~~~~~~~~~~~~

    "Quis custodiet ipsos custodes?"

       -- "Who will police the police?", or in this case:

    Who will test the test?

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

from cStringIO import StringIO
from werkzeug.wrappers import Request, Response
from werkzeug.test import Client, EnvironBuilder


def cookie_app(environ, start_response):
    """A WSGI application which sets a cookie, and returns as a ersponse any
    cookie which exists.
    """
    response = Response(environ.get('HTTP_COOKIE', 'No Cookie'),
                        mimetype='text/plain')
    response.set_cookie('test', 'test')
    return response(environ, start_response)


def test_set_cookie_app():
    """Test that a server cookie is set and stored in the client
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'Set-Cookie' in dict(headers)


def test_cookiejar_stores_cookie():
    """Test that the cookie jar in the test client stores the cookie
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'test' in c.cookie_jar._cookies['localhost.local']['/']


def test_no_initial_cookie():
    """Test there is no cookie set in the client initially.
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_resent_cookie():
    """Test that the client resends cookies on subsequent requests,
    """
    c = Client(cookie_app)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'test=test'


def test_disable_cookies():
    """Ensure that cookies are not stored when use_cookies is False in the
    client.
    """
    c = Client(cookie_app, use_cookies=False)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_cookie_for_different_path():
    """Test that the client resends cookies on subsequent requests for
    different paths.
    """
    c = Client(cookie_app)
    c.open('/path1')
    appiter, code, headers = c.open('/path2')
    assert ''.join(appiter) == 'test=test'


def test_environ_builder_basics():
    """Test EnvironBuilder basics"""
    b = EnvironBuilder()
    assert b.content_type is None
    b.method = 'POST'
    assert b.content_type == 'application/x-www-form-urlencoded'
    b.files.add_file('test', StringIO('test contents'), 'test.txt')
    assert b.files['test'].content_type == 'text/plain'
    assert b.content_type == 'multipart/form-data'
    b.form['test'] = 'normal value'

    req = b.get_request()
    b.close()

    assert req.url == 'http://localhost/'
    assert req.method == 'POST'
    assert req.form['test'] == 'normal value'
    assert req.files['test'].content_type == 'text/plain'
    assert req.files['test'].filename == 'test.txt'
    assert req.files['test'].read() == 'test contents'


def test_environ_builder_headers():
    """Test EnvironBuilder headers and environ overrides"""
    b = EnvironBuilder(environ_base={'HTTP_USER_AGENT': 'Foo/0.1'},
                       environ_overrides={'wsgi.version': (1, 1)})
    b.headers['X-Suck-My-Dick'] = 'very well sir'
    env = b.get_environ()
    assert env['HTTP_USER_AGENT'] == 'Foo/0.1'
    assert env['HTTP_X_SUCK_MY_DICK'] == 'very well sir'
    assert env['wsgi.version'] == (1, 1)

    b.headers['User-Agent'] = 'Bar/1.0'
    env = b.get_environ()
    assert env['HTTP_USER_AGENT'] == 'Bar/1.0'


def test_environ_builder_paths():
    """Test EnvironBuilder with different paths"""
    b = EnvironBuilder(path='/foo', base_url='http://example.com/')
    assert b.base_url == 'http://example.com/'
    assert b.path == '/foo'
    assert b.script_root == ''
    assert b.host == 'example.com'

    b = EnvironBuilder(path='/foo', base_url='http://example.com/bar')
    assert b.base_url == 'http://example.com/bar/'
    assert b.path == '/foo'
    assert b.script_root == '/bar'
    assert b.host == 'example.com'

    b.host = 'localhost'
    assert b.base_url == 'http://localhost/bar/'
    b.base_url = 'http://localhost:8080/'
    assert b.host == 'localhost:8080'
    assert b.server_name == 'localhost'
    assert b.server_port == 8080

    b.host = 'foo.invalid'
    b.url_scheme = 'https'
    b.script_root = '/test'
    env = b.get_environ()
    assert env['SERVER_NAME'] == 'foo.invalid'
    assert env['SERVER_PORT'] == '443'
    assert env['SCRIPT_NAME'] == '/test'
    assert env['PATH_INFO'] == '/foo'
    assert env['HTTP_HOST'] == 'foo.invalid'
    assert env['wsgi.url_scheme'] == 'https'
    assert b.base_url == 'https://foo.invalid/test/'
