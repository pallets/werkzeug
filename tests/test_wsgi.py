# -*- coding: utf-8 -*-
"""
    werkzeug.wsgi test
    ~~~~~~~~~~~~~~~~~~

    Tests the WSGI utilities.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os import path
from cStringIO import StringIO

from nose.tools import assert_raises

from werkzeug import Client, create_environ, BaseResponse, run_wsgi_app
from werkzeug.exceptions import BadRequest

from werkzeug.wsgi import SharedDataMiddleware, get_host, responder, \
     LimitedStream, pop_path_info, peek_path_info


def test_shareddatamiddleware_get_file_loader():
    """Shared middleware file loader lookup"""
    app = SharedDataMiddleware(None, {})
    assert callable(app.get_file_loader('foo'))


def test_shared_data_middleware():
    """Shared data middleware"""
    def null_application(environ, start_response):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        yield 'NOT FOUND'
    app = SharedDataMiddleware(null_application, {
        '/':        path.join(path.dirname(__file__), 'res'),
        '/sources': path.join(path.dirname(__file__), 'res'),
        '/pkg':     ('werkzeug.debug', 'shared')
    })

    for p in '/test.txt', '/sources/test.txt':
        app_iter, status, headers = run_wsgi_app(app, create_environ(p))
        assert status == '200 OK'
        assert ''.join(app_iter).strip() == 'FOUND'

    app_iter, status, headers = run_wsgi_app(app, create_environ('/pkg/body.tmpl'))
    contents = ''.join(app_iter)
    assert 'Werkzeug Debugger' in contents

    app_iter, status, headers = run_wsgi_app(app, create_environ('/missing'))
    assert status == '404 NOT FOUND'
    assert ''.join(app_iter).strip() == 'NOT FOUND'


def test_get_host():
    """Host lookup"""
    env = {'HTTP_X_FORWARDED_HOST': 'example.org',
           'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
    assert get_host(env) == 'example.org'
    assert get_host(create_environ('/', 'http://example.org')) \
        == 'example.org'


def test_responder():
    """Responder decorator"""
    def foo(environ, start_response):
        return BaseResponse('Test')
    client = Client(responder(foo), BaseResponse)
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == 'Test'


def test_pop_path_info():
    """Test path info popping in the utils"""
    original_env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b///c'}

    # regular path info popping
    def assert_tuple(script_name, path_info):
        assert env.get('SCRIPT_NAME') == script_name
        assert env.get('PATH_INFO') == path_info
    env = original_env.copy()
    pop = lambda: pop_path_info(env)

    assert_tuple('/foo', '/a/b///c')
    assert pop() == 'a'
    assert_tuple('/foo/a', '/b///c')
    assert pop() == 'b'
    assert_tuple('/foo/a/b', '///c')
    assert pop() == 'c'
    assert_tuple('/foo/a/b///c', '')
    assert pop() is None


def test_peek_path_info():
    """Test path info peeking in wrappers and utils"""
    env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/aaa/b///c'}

    assert peek_path_info(env) == 'aaa'
    assert peek_path_info(env) == 'aaa'


def test_limited_stream():
    """Test the LimitedStream"""
    io = StringIO('123456')
    stream = LimitedStream(io, 3, False)
    assert stream.read() == '123'
    assert_raises(BadRequest, stream.read)

    io = StringIO('123456')
    stream = LimitedStream(io, 3, False)
    assert stream.read(1) == '1'
    assert stream.read(1) == '2'
    assert stream.read(1) == '3'
    assert_raises(BadRequest, stream.read)

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readline() == '123456\n'
    assert stream.readline() == 'ab'

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines() == ['123456\n', 'ab']

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines(2) == ['12']
    assert stream.readlines(2) == ['34']
    assert stream.readlines() == ['56\n', 'ab']

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readline(100) == '123456\n'

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines(100) == ['123456\n', 'ab']

    io = StringIO('123456')
    stream = LimitedStream(io, 3)
    assert stream.read(1) == '1'
    assert stream.read(1) == '2'
    assert stream.read() == '3'
    assert stream.read() == ''
