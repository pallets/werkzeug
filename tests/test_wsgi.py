# -*- coding: utf-8 -*-
"""
    tests.wsgi
    ~~~~~~~~~~

    Tests the WSGI utilities.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

from os import path
from contextlib import closing

from tests import strict_eq

from werkzeug.wrappers import BaseResponse
from werkzeug.exceptions import BadRequest, ClientDisconnected
from werkzeug.test import Client, create_environ, run_wsgi_app
from werkzeug import wsgi
from werkzeug._compat import StringIO, BytesIO, NativeStringIO, to_native, \
    to_bytes


def test_shareddatamiddleware_get_file_loader():
    app = wsgi.SharedDataMiddleware(None, {})
    assert callable(app.get_file_loader('foo'))

def test_shared_data_middleware(tmpdir):
    def null_application(environ, start_response):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        yield b'NOT FOUND'

    test_dir = str(tmpdir)
    with open(path.join(test_dir, to_native(u'äöü', 'utf-8')), 'w') as test_file:
        test_file.write(u'FOUND')

    app = wsgi.SharedDataMiddleware(null_application, {
        '/':        path.join(path.dirname(__file__), 'res'),
        '/sources': path.join(path.dirname(__file__), 'res'),
        '/pkg':     ('werkzeug.debug', 'shared'),
        '/foo':     test_dir
    })

    for p in '/test.txt', '/sources/test.txt', '/foo/äöü':
        app_iter, status, headers = run_wsgi_app(app, create_environ(p))
        assert status == '200 OK'
        with closing(app_iter) as app_iter:
            data = b''.join(app_iter).strip()
        assert data == b'FOUND'

    app_iter, status, headers = run_wsgi_app(
        app, create_environ('/pkg/debugger.js'))
    with closing(app_iter) as app_iter:
        contents = b''.join(app_iter)
    assert b'$(function() {' in contents

    app_iter, status, headers = run_wsgi_app(
        app, create_environ('/missing'))
    assert status == '404 NOT FOUND'
    assert b''.join(app_iter).strip() == b'NOT FOUND'

def test_dispatchermiddleware():
    def null_application(environ, start_response):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        yield b'NOT FOUND'

    def dummy_application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield to_bytes(environ['SCRIPT_NAME'])

    app = wsgi.DispatcherMiddleware(null_application, {
        '/test1': dummy_application,
        '/test2/very': dummy_application,
        })
    tests = {
        '/test1': ('/test1', '/test1/asfd', '/test1/very'),
        '/test2/very': ('/test2/very', '/test2/very/long/path/after/script/name')
        }
    for name, urls in tests.items():
        for p in urls:
            environ = create_environ(p)
            app_iter, status, headers = run_wsgi_app(app, environ)
            assert status == '200 OK'
            assert b''.join(app_iter).strip() == to_bytes(name)

    app_iter, status, headers = run_wsgi_app(
        app, create_environ('/missing'))
    assert status == '404 NOT FOUND'
    assert b''.join(app_iter).strip() == b'NOT FOUND'

def test_get_host():
    env = {'HTTP_X_FORWARDED_HOST': 'example.org',
           'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
    assert wsgi.get_host(env) == 'example.org'
    assert wsgi.get_host(create_environ('/', 'http://example.org')) == \
        'example.org'

def test_get_host_multiple_forwarded():
    env = {'HTTP_X_FORWARDED_HOST': 'example.com, example.org',
           'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
    assert wsgi.get_host(env) == 'example.com'
    assert wsgi.get_host(create_environ('/', 'http://example.com')) == \
        'example.com'

def test_get_host_validation():
    env = {'HTTP_X_FORWARDED_HOST': 'example.org',
           'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
    assert wsgi.get_host(env, trusted_hosts=['.example.org']) == 'example.org'
    pytest.raises(BadRequest, wsgi.get_host, env,
                       trusted_hosts=['example.com'])

def test_responder():
    def foo(environ, start_response):
        return BaseResponse(b'Test')
    client = Client(wsgi.responder(foo), BaseResponse)
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == b'Test'

def test_pop_path_info():
    original_env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b///c'}

    # regular path info popping
    def assert_tuple(script_name, path_info):
        assert env.get('SCRIPT_NAME') == script_name
        assert env.get('PATH_INFO') == path_info
    env = original_env.copy()
    pop = lambda: wsgi.pop_path_info(env)

    assert_tuple('/foo', '/a/b///c')
    assert pop() == 'a'
    assert_tuple('/foo/a', '/b///c')
    assert pop() == 'b'
    assert_tuple('/foo/a/b', '///c')
    assert pop() == 'c'
    assert_tuple('/foo/a/b///c', '')
    assert pop() is None

def test_peek_path_info():
    env = {
        'SCRIPT_NAME': '/foo',
        'PATH_INFO': '/aaa/b///c'
    }

    assert wsgi.peek_path_info(env) == 'aaa'
    assert wsgi.peek_path_info(env) == 'aaa'
    assert wsgi.peek_path_info(env, charset=None) == b'aaa'
    assert wsgi.peek_path_info(env, charset=None) == b'aaa'

def test_path_info_and_script_name_fetching():
    env = create_environ(u'/\N{SNOWMAN}', u'http://example.com/\N{COMET}/')
    assert wsgi.get_path_info(env) == u'/\N{SNOWMAN}'
    assert wsgi.get_path_info(env, charset=None) == u'/\N{SNOWMAN}'.encode('utf-8')
    assert wsgi.get_script_name(env) == u'/\N{COMET}'
    assert wsgi.get_script_name(env, charset=None) == u'/\N{COMET}'.encode('utf-8')

def test_query_string_fetching():
    env = create_environ(u'/?\N{SNOWMAN}=\N{COMET}')
    qs = wsgi.get_query_string(env)
    strict_eq(qs, '%E2%98%83=%E2%98%84')

def test_limited_stream():
    class RaisingLimitedStream(wsgi.LimitedStream):
        def on_exhausted(self):
            raise BadRequest('input stream exhausted')

    io = BytesIO(b'123456')
    stream = RaisingLimitedStream(io, 3)
    strict_eq(stream.read(), b'123')
    pytest.raises(BadRequest, stream.read)

    io = BytesIO(b'123456')
    stream = RaisingLimitedStream(io, 3)
    strict_eq(stream.tell(), 0)
    strict_eq(stream.read(1), b'1')
    strict_eq(stream.tell(), 1)
    strict_eq(stream.read(1), b'2')
    strict_eq(stream.tell(), 2)
    strict_eq(stream.read(1), b'3')
    strict_eq(stream.tell(), 3)
    pytest.raises(BadRequest, stream.read)

    io = BytesIO(b'123456\nabcdefg')
    stream = wsgi.LimitedStream(io, 9)
    strict_eq(stream.readline(), b'123456\n')
    strict_eq(stream.readline(), b'ab')

    io = BytesIO(b'123456\nabcdefg')
    stream = wsgi.LimitedStream(io, 9)
    strict_eq(stream.readlines(), [b'123456\n', b'ab'])

    io = BytesIO(b'123456\nabcdefg')
    stream = wsgi.LimitedStream(io, 9)
    strict_eq(stream.readlines(2), [b'12'])
    strict_eq(stream.readlines(2), [b'34'])
    strict_eq(stream.readlines(), [b'56\n', b'ab'])

    io = BytesIO(b'123456\nabcdefg')
    stream = wsgi.LimitedStream(io, 9)
    strict_eq(stream.readline(100), b'123456\n')

    io = BytesIO(b'123456\nabcdefg')
    stream = wsgi.LimitedStream(io, 9)
    strict_eq(stream.readlines(100), [b'123456\n', b'ab'])

    io = BytesIO(b'123456')
    stream = wsgi.LimitedStream(io, 3)
    strict_eq(stream.read(1), b'1')
    strict_eq(stream.read(1), b'2')
    strict_eq(stream.read(), b'3')
    strict_eq(stream.read(), b'')

    io = BytesIO(b'123456')
    stream = wsgi.LimitedStream(io, 3)
    strict_eq(stream.read(-1), b'123')

    io = BytesIO(b'123456')
    stream = wsgi.LimitedStream(io, 0)
    strict_eq(stream.read(-1), b'')

    io = StringIO(u'123456')
    stream = wsgi.LimitedStream(io, 0)
    strict_eq(stream.read(-1), u'')

    io = StringIO(u'123\n456\n')
    stream = wsgi.LimitedStream(io, 8)
    strict_eq(list(stream), [u'123\n', u'456\n'])

def test_limited_stream_disconnection():
    io = BytesIO(b'A bit of content')

    # disconnect detection on out of bytes
    stream = wsgi.LimitedStream(io, 255)
    with pytest.raises(ClientDisconnected):
        stream.read()

    # disconnect detection because file close
    io = BytesIO(b'x' * 255)
    io.close()
    stream = wsgi.LimitedStream(io, 255)
    with pytest.raises(ClientDisconnected):
        stream.read()

def test_path_info_extraction():
    x = wsgi.extract_path_info('http://example.com/app', '/app/hello')
    assert x == u'/hello'
    x = wsgi.extract_path_info('http://example.com/app',
                               'https://example.com/app/hello')
    assert x == u'/hello'
    x = wsgi.extract_path_info('http://example.com/app/',
                               'https://example.com/app/hello')
    assert x == u'/hello'
    x = wsgi.extract_path_info('http://example.com/app/',
                               'https://example.com/app')
    assert x == u'/'
    x = wsgi.extract_path_info(u'http://☃.net/', u'/fööbär')
    assert x == u'/fööbär'
    x = wsgi.extract_path_info(u'http://☃.net/x', u'http://☃.net/x/fööbär')
    assert x == u'/fööbär'

    env = create_environ(u'/fööbär', u'http://☃.net/x/')
    x = wsgi.extract_path_info(env, u'http://☃.net/x/fööbär')
    assert x == u'/fööbär'

    x = wsgi.extract_path_info('http://example.com/app/',
                               'https://example.com/a/hello')
    assert x is None
    x = wsgi.extract_path_info('http://example.com/app/',
                               'https://example.com/app/hello',
                               collapse_http_schemes=False)
    assert x is None

def test_get_host_fallback():
    assert wsgi.get_host({
        'SERVER_NAME':      'foobar.example.com',
        'wsgi.url_scheme':  'http',
        'SERVER_PORT':      '80'
    }) == 'foobar.example.com'
    assert wsgi.get_host({
        'SERVER_NAME':      'foobar.example.com',
        'wsgi.url_scheme':  'http',
        'SERVER_PORT':      '81'
    }) == 'foobar.example.com:81'

def test_get_current_url_unicode():
    env = create_environ()
    env['QUERY_STRING'] = 'foo=bar&baz=blah&meh=\xcf'
    rv = wsgi.get_current_url(env)
    strict_eq(rv,
        u'http://localhost/?foo=bar&baz=blah&meh=\ufffd')

def test_multi_part_line_breaks():
    data = 'abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK'
    test_stream = NativeStringIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data),
                                     buffer_size=16))
    assert lines == ['abcdef\r\n', 'ghijkl\r\n', 'mnopqrstuvwxyz\r\n',
                     'ABCDEFGHIJK']

    data = 'abc\r\nThis line is broken by the buffer length.' \
        '\r\nFoo bar baz'
    test_stream = NativeStringIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data),
                                     buffer_size=24))
    assert lines == ['abc\r\n', 'This line is broken by the buffer '
                     'length.\r\n', 'Foo bar baz']

def test_multi_part_line_breaks_bytes():
    data = b'abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK'
    test_stream = BytesIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data),
                                     buffer_size=16))
    assert lines == [b'abcdef\r\n', b'ghijkl\r\n', b'mnopqrstuvwxyz\r\n',
                     b'ABCDEFGHIJK']

    data = b'abc\r\nThis line is broken by the buffer length.' \
        b'\r\nFoo bar baz'
    test_stream = BytesIO(data)
    lines = list(wsgi.make_line_iter(test_stream, limit=len(data),
                                     buffer_size=24))
    assert lines == [b'abc\r\n', b'This line is broken by the buffer '
                     b'length.\r\n', b'Foo bar baz']

def test_multi_part_line_breaks_problematic():
    data = 'abc\rdef\r\nghi'
    for x in range(1, 10):
        test_stream = NativeStringIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data),
                                         buffer_size=4))
        assert lines == ['abc\r', 'def\r\n', 'ghi']

def test_iter_functions_support_iterators():
    data = ['abcdef\r\nghi', 'jkl\r\nmnopqrstuvwxyz\r', '\nABCDEFGHIJK']
    lines = list(wsgi.make_line_iter(data))
    assert lines == ['abcdef\r\n', 'ghijkl\r\n', 'mnopqrstuvwxyz\r\n',
                     'ABCDEFGHIJK']

def test_make_chunk_iter():
    data = [u'abcdefXghi', u'jklXmnopqrstuvwxyzX', u'ABCDEFGHIJK']
    rv = list(wsgi.make_chunk_iter(data, 'X'))
    assert rv == [u'abcdef', u'ghijkl', u'mnopqrstuvwxyz', u'ABCDEFGHIJK']

    data = u'abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK'
    test_stream = StringIO(data)
    rv = list(wsgi.make_chunk_iter(test_stream, 'X', limit=len(data),
                                   buffer_size=4))
    assert rv == [u'abcdef', u'ghijkl', u'mnopqrstuvwxyz', u'ABCDEFGHIJK']

def test_make_chunk_iter_bytes():
    data = [b'abcdefXghi', b'jklXmnopqrstuvwxyzX', b'ABCDEFGHIJK']
    rv = list(wsgi.make_chunk_iter(data, 'X'))
    assert rv == [b'abcdef', b'ghijkl', b'mnopqrstuvwxyz', b'ABCDEFGHIJK']

    data = b'abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK'
    test_stream = BytesIO(data)
    rv = list(wsgi.make_chunk_iter(test_stream, 'X', limit=len(data),
                                   buffer_size=4))
    assert rv == [b'abcdef', b'ghijkl', b'mnopqrstuvwxyz', b'ABCDEFGHIJK']

def test_lines_longer_buffer_size():
    data = '1234567890\n1234567890\n'
    for bufsize in range(1, 15):
        lines = list(wsgi.make_line_iter(NativeStringIO(data), limit=len(data),
                                         buffer_size=4))
        assert lines == ['1234567890\n', '1234567890\n']
