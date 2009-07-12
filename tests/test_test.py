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

import sys
from cStringIO import StringIO
from nose.tools import assert_raises
from werkzeug.wrappers import Request, Response, BaseResponse
from werkzeug.test import Client, EnvironBuilder, create_environ
from werkzeug.utils import redirect, get_host
from werkzeug.datastructures import Headers


def cookie_app(environ, start_response):
    """A WSGI application which sets a cookie, and returns as a ersponse any
    cookie which exists.
    """
    response = Response(environ.get('HTTP_COOKIE', 'No Cookie'),
                        mimetype='text/plain')
    response.set_cookie('test', 'test')
    return response(environ, start_response)


def redirect_demo_app(environ, start_response):
    response = redirect('http://localhost/some/redirect/')
    return response(environ, start_response)


def external_redirect_demo_app(environ, start_response):
    response = redirect('http://example.org/')
    return response(environ, start_response)


def test_set_cookie_app():
    """Test that a server cookie is set and stored in the client"""
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'Set-Cookie' in dict(headers)


def test_cookiejar_stores_cookie():
    """Test that the cookie jar in the test client stores the cookie"""
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'test' in c.cookie_jar._cookies['localhost.local']['/']


def test_no_initial_cookie():
    """Test there is no cookie set in the client initially"""
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_resent_cookie():
    """Test that the client resends cookies on subsequent requests
    """
    c = Client(cookie_app)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'test=test'


def test_disable_cookies():
    """Ensure that cookies are not stored when use_cookies is False in the
    client
    """
    c = Client(cookie_app, use_cookies=False)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_cookie_for_different_path():
    """Test that the client resends cookies on subsequent requests for
    different paths
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


def test_environ_builder_content_type():
    """EnvironBuilder content type behavior"""
    builder = EnvironBuilder()
    assert builder.content_type is None
    builder.method = 'POST'
    assert builder.content_type == 'application/x-www-form-urlencoded'
    builder.form['foo'] = 'bar'
    assert builder.content_type == 'application/x-www-form-urlencoded'
    builder.files.add_file('blafasel', StringIO('foo'), 'test.txt')
    assert builder.content_type == 'multipart/form-data'
    req = builder.get_request()
    assert req.form['foo'] == 'bar'
    assert req.files['blafasel'].read() == 'foo'


def test_environ_builder_stream_switch():
    """EnvironBuilder stream switch"""
    from cStringIO import OutputType
    from werkzeug.test import stream_encode_multipart
    from werkzeug import url_decode, MultiDict, parse_form_data

    d = MultiDict(dict(foo=u'bar', blub=u'blah', hu=u'hum'))
    for use_tempfile in False, True:
        stream, length, boundary = stream_encode_multipart(
            d, use_tempfile, threshold=150)
        assert isinstance(stream, OutputType) != use_tempfile

        form = parse_form_data({'wsgi.input': stream, 'CONTENT_LENGTH': str(length),
                                'CONTENT_TYPE': 'multipart/form-data; boundary="%s"' %
                                boundary})[1]
        assert form == d


def test_create_environ():
    """Environment creation helper"""
    env = create_environ('/foo?bar=baz', 'http://example.org/')
    expected = {
        'wsgi.multiprocess':    False,
        'wsgi.version':         (1, 0),
        'wsgi.run_once':        False,
        'wsgi.errors':          sys.stderr,
        'wsgi.multithread':     False,
        'wsgi.url_scheme':      'http',
        'SCRIPT_NAME':          '',
        'CONTENT_TYPE':         '',
        'CONTENT_LENGTH':       '0',
        'SERVER_NAME':          'example.org',
        'REQUEST_METHOD':       'GET',
        'HTTP_HOST':            'example.org',
        'PATH_INFO':            '/foo',
        'SERVER_PORT':          '80',
        'SERVER_PROTOCOL':      'HTTP/1.1',
        'QUERY_STRING':         'bar=baz'
    }
    for key, value in expected.iteritems():
        assert env[key] == value
    assert env['wsgi.input'].read(0) == ''

    assert create_environ('/foo', 'http://example.com/')['SCRIPT_NAME'] == ''


def test_file_closing():
    """Test automatic closing of files in EnvironBuilder and friends"""
    closed = []
    class SpecialInput(object):
        def read(self):
            return ''
        def close(self):
            closed.append(self)

    env = create_environ(data={'foo': SpecialInput()})
    assert len(closed) == 1
    builder = EnvironBuilder()
    builder.files.add_file('blah', SpecialInput())
    builder.close()
    assert len(closed) == 2


def test_follow_redirect():
    env = create_environ('/', base_url='http://localhost')
    c = Client(redirect_demo_app)
    headers = Headers(c.open(environ_overrides=env, follow_redirects=True)[2])
    assert headers['Location'] == 'http://localhost/some/redirect/'


def test_follow_external_redirect():
    env = create_environ('/', base_url='http://localhost')
    c = Client(external_redirect_demo_app)
    assert_raises(RuntimeError, lambda: c.open(environ_overrides=env, follow_redirects=True))


def test_follow_redirect_with_response_wrapper():
    # Test that the :cls:`Client` is aware of user defined response wrappers
    env = create_environ('/', 'http://localhost')
    c = Client(redirect_demo_app, response_wrapper=BaseResponse)
    resp = c.post(environ_overrides=env, follow_redirects=True, data='foo=blub+hehe&blah=42')
    assert isinstance(resp, BaseResponse)
    assert resp.headers['Location'] == 'http://localhost/some/redirect/'
