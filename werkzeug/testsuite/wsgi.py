# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.wsgi
    ~~~~~~~~~~~~~~~~~~~~~~~

    Tests the WSGI utilities.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement

import unittest
from os import path
try:
    from io import BytesIO
except ImportError:
    from cStringIO import StringIO as BytesIO

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug._internal import _b
from werkzeug.wrappers import BaseResponse
from werkzeug.exceptions import BadRequest, ClientDisconnected
from werkzeug.test import Client, create_environ, run_wsgi_app
from werkzeug import wsgi


class WSGIUtilsTestCase(WerkzeugTestCase):

    def test_shareddatamiddleware_get_file_loader(self):
        app = wsgi.SharedDataMiddleware(None, {})
        assert callable(app.get_file_loader('foo'))

    def test_shared_data_middleware(self):
        def null_application(environ, start_response):
            start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
            yield _b('NOT FOUND')
        app = wsgi.SharedDataMiddleware(null_application, {
            '/':        path.join(path.dirname(__file__), 'res'),
            '/sources': path.join(path.dirname(__file__), 'res'),
            '/pkg':     ('werkzeug.debug', 'shared')
        })

        for p in '/test.txt', '/sources/test.txt':
            app_iter, status, headers = run_wsgi_app(app, create_environ(p))
            self.assert_equal(status, '200 OK')
            self.assert_equal(_b('').join(app_iter).strip(), _b('FOUND'))

        app_iter, status, headers = run_wsgi_app(app, create_environ('/pkg/debugger.js'))
        contents = _b('').join(app_iter)
        assert _b('$(function() {') in contents

        app_iter, status, headers = run_wsgi_app(app, create_environ('/missing'))
        self.assert_equal(status, '404 NOT FOUND')
        self.assert_equal(_b('').join(app_iter).strip(), _b('NOT FOUND'))

    def test_get_host(self):
        env = {'HTTP_X_FORWARDED_HOST': 'example.org',
               'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
        self.assert_equal(wsgi.get_host(env), 'example.org')
        assert wsgi.get_host(create_environ('/', 'http://example.org')) \
            == 'example.org'

    def test_responder(self):
        def foo(environ, start_response):
            return BaseResponse(_b('Test'))
        client = Client(wsgi.responder(foo), BaseResponse)
        response = client.get('/')
        self.assert_equal(response.status_code, 200)
        self.assert_equal(response.data, _b('Test'))

    def test_pop_path_info(self):
        original_env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b///c'}

        # regular path info popping
        def assert_tuple(script_name, path_info):
            self.assert_equal(env.get('SCRIPT_NAME'), script_name)
            self.assert_equal(env.get('PATH_INFO'), path_info)
        env = original_env.copy()
        pop = lambda: wsgi.pop_path_info(env)

        assert_tuple('/foo', '/a/b///c')
        self.assert_equal(pop(), 'a')
        assert_tuple('/foo/a', '/b///c')
        self.assert_equal(pop(), 'b')
        assert_tuple('/foo/a/b', '///c')
        self.assert_equal(pop(), 'c')
        assert_tuple('/foo/a/b///c', '')
        assert pop() is None

    def test_peek_path_info(self):
        env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/aaa/b///c'}

        self.assert_equal(wsgi.peek_path_info(env), 'aaa')
        self.assert_equal(wsgi.peek_path_info(env), 'aaa')

    def test_limited_stream(self):
        class RaisingLimitedStream(wsgi.LimitedStream):
            def on_exhausted(self):
                raise BadRequest('input stream exhausted')

        io = BytesIO(_b('123456'))
        stream = RaisingLimitedStream(io, 3)
        self.assert_equal(stream.read(), _b('123'))
        self.assert_raises(BadRequest, stream.read)

        io = BytesIO(_b('123456'))
        stream = RaisingLimitedStream(io, 3)
        self.assert_equal(stream.tell(), 0)
        self.assert_equal(stream.read(1), _b('1'))
        self.assert_equal(stream.tell(), 1)
        self.assert_equal(stream.read(1), _b('2'))
        self.assert_equal(stream.tell(), 2)
        self.assert_equal(stream.read(1), _b('3'))
        self.assert_equal(stream.tell(), 3)
        self.assert_raises(BadRequest, stream.read)

        io = BytesIO(_b('123456\nabcdefg'))
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readline(), _b('123456\n'))
        self.assert_equal(stream.readline(), _b('ab'))

        io = BytesIO(_b('123456\nabcdefg'))
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(), [_b('123456\n'), _b('ab')])

        io = BytesIO(_b('123456\nabcdefg'))
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(2), [_b('12')])
        self.assert_equal(stream.readlines(2), [_b('34')])
        self.assert_equal(stream.readlines(), [_b('56\n'), _b('ab')])

        io = BytesIO(_b('123456\nabcdefg'))
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readline(100), _b('123456\n'))

        io = BytesIO(_b('123456\nabcdefg'))
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(100), [_b('123456\n'), _b('ab')])

        io = BytesIO(_b('123456'))
        stream = wsgi.LimitedStream(io, 3)
        self.assert_equal(stream.read(1), _b('1'))
        self.assert_equal(stream.read(1), _b('2'))
        self.assert_equal(stream.read(), _b('3'))
        self.assert_equal(stream.read(), _b(''))

        io = BytesIO(_b('123456'))
        stream = wsgi.LimitedStream(io, 3)
        self.assert_equal(stream.read(-1), _b('123'))

    def test_limited_stream_disconnection(self):
        io = BytesIO(_b('A bit of content'))

        # disconnect detection on out of bytes
        stream = wsgi.LimitedStream(io, 255)
        with self.assert_raises(ClientDisconnected):
            stream.read()

        # disconnect detection because file close
        io = BytesIO(_b('x' * 255))
        io.close()
        stream = wsgi.LimitedStream(io, 255)
        with self.assert_raises(ClientDisconnected):
            stream.read()

    def test_path_info_extraction(self):
        x = wsgi.extract_path_info('http://example.com/app', '/app/hello')
        self.assert_equal(x, u'/hello')
        x = wsgi.extract_path_info('http://example.com/app',
                                   'https://example.com/app/hello')
        self.assert_equal(x, u'/hello')
        x = wsgi.extract_path_info('http://example.com/app/',
                                   'https://example.com/app/hello')
        self.assert_equal(x, u'/hello')
        x = wsgi.extract_path_info('http://example.com/app/',
                                   'https://example.com/app')
        self.assert_equal(x, u'/')
        x = wsgi.extract_path_info(u'http://☃.net/', u'/fööbär')
        self.assert_equal(x, u'/fööbär')
        x = wsgi.extract_path_info(u'http://☃.net/x', u'http://☃.net/x/fööbär')
        self.assert_equal(x, u'/fööbär')

        env = create_environ(u'/fööbär', u'http://☃.net/x/')
        x = wsgi.extract_path_info(env, u'http://☃.net/x/fööbär')
        self.assert_equal(x, u'/fööbär')

        x = wsgi.extract_path_info('http://example.com/app/',
                                   'https://example.com/a/hello')
        assert x is None
        x = wsgi.extract_path_info('http://example.com/app/',
                                   'https://example.com/app/hello',
                                   collapse_http_schemes=False)
        assert x is None

    def test_get_host_fallback(self):
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

    def test_multi_part_line_breaks(self):
        data = _b('abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK')
        test_stream = BytesIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=16))
        self.assert_equal(lines, [_b('abcdef\r\n'), _b('ghijkl\r\n'), _b('mnopqrstuvwxyz\r\n'), _b('ABCDEFGHIJK')])

        data = _b('abc\r\nThis line is broken by the buffer length.\r\nFoo bar baz')
        test_stream = BytesIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=24))
        self.assert_equal(lines, [_b('abc\r\n'), _b('This line is broken by the buffer length.\r\n'), _b('Foo bar baz')])

    def test_multi_part_line_breaks_problematic(self):
        data = _b('abc\rdef\r\nghi')
        for x in xrange(1, 10):
            test_stream = BytesIO(data)
            lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=4))
            assert lines == [_b('abc\r'), _b('def\r\n'), _b('ghi')]

    def test_iter_functions_support_iterators(self):
        data = [_b('abcdef\r\nghi'), _b('jkl\r\nmnopqrstuvwxyz\r'), _b('\nABCDEFGHIJK')]
        lines = list(wsgi.make_line_iter(data))
        self.assert_equal(lines, [_b('abcdef\r\n'), _b('ghijkl\r\n'), _b('mnopqrstuvwxyz\r\n'), _b('ABCDEFGHIJK')])

    def test_make_chunk_iter(self):
        data = [_b('abcdefXghi'), _b('jklXmnopqrstuvwxyzX'), _b('ABCDEFGHIJK')]
        rv = list(wsgi.make_chunk_iter(data, 'X'))
        self.assert_equal(rv, [_b('abcdef'), _b('ghijkl'), _b('mnopqrstuvwxyz'), _b('ABCDEFGHIJK')])

        data = _b('abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK')
        test_stream = BytesIO(data)
        rv = list(wsgi.make_chunk_iter(test_stream, 'X', limit=len(data), buffer_size=4))
        self.assert_equal(rv, [_b('abcdef'), _b('ghijkl'), _b('mnopqrstuvwxyz'), _b('ABCDEFGHIJK')])

    def test_lines_longer_buffer_size(self):
        data = _b('1234567890\n1234567890\n')
        for bufsize in xrange(1, 15):
            lines = list(wsgi.make_line_iter(BytesIO(data), limit=len(data), buffer_size=4))
            self.assert_equal(lines, [_b('1234567890\n'), _b('1234567890\n')])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WSGIUtilsTestCase))
    return suite
