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
from cStringIO import StringIO

from werkzeug.testsuite import WerkzeugTestCase

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
            yield 'NOT FOUND'
        app = wsgi.SharedDataMiddleware(null_application, {
            '/':        path.join(path.dirname(__file__), 'res'),
            '/sources': path.join(path.dirname(__file__), 'res'),
            '/pkg':     ('werkzeug.debug', 'shared')
        })

        for p in '/test.txt', '/sources/test.txt':
            app_iter, status, headers = run_wsgi_app(app, create_environ(p))
            self.assert_equal(status, '200 OK')
            self.assert_equal(''.join(app_iter).strip(), 'FOUND')

        app_iter, status, headers = run_wsgi_app(app, create_environ('/pkg/debugger.js'))
        contents = ''.join(app_iter)
        assert '$(function() {' in contents

        app_iter, status, headers = run_wsgi_app(app, create_environ('/missing'))
        self.assert_equal(status, '404 NOT FOUND')
        self.assert_equal(''.join(app_iter).strip(), 'NOT FOUND')

    def test_get_host(self):
        env = {'HTTP_X_FORWARDED_HOST': 'example.org',
               'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
        self.assert_equal(wsgi.get_host(env), 'example.org')
        assert wsgi.get_host(create_environ('/', 'http://example.org')) \
            == 'example.org'

    def test_get_host_validation(self):
        env = {'HTTP_X_FORWARDED_HOST': 'example.org',
               'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
        self.assert_equal(wsgi.get_host(env, trusted_hosts=['.example.org']),
                          'example.org')
        self.assert_raises(BadRequest, wsgi.get_host, env, trusted_hosts=['example.com'])

    def test_responder(self):
        def foo(environ, start_response):
            return BaseResponse('Test')
        client = Client(wsgi.responder(foo), BaseResponse)
        response = client.get('/')
        self.assert_equal(response.status_code, 200)
        self.assert_equal(response.data, 'Test')

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

        io = StringIO('123456')
        stream = RaisingLimitedStream(io, 3)
        self.assert_equal(stream.read(), '123')
        self.assert_raises(BadRequest, stream.read)

        io = StringIO('123456')
        stream = RaisingLimitedStream(io, 3)
        self.assert_equal(stream.tell(), 0)
        self.assert_equal(stream.read(1), '1')
        self.assert_equal(stream.tell(), 1)
        self.assert_equal(stream.read(1), '2')
        self.assert_equal(stream.tell(), 2)
        self.assert_equal(stream.read(1), '3')
        self.assert_equal(stream.tell(), 3)
        self.assert_raises(BadRequest, stream.read)

        io = StringIO('123456\nabcdefg')
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readline(), '123456\n')
        self.assert_equal(stream.readline(), 'ab')

        io = StringIO('123456\nabcdefg')
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(), ['123456\n', 'ab'])

        io = StringIO('123456\nabcdefg')
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(2), ['12'])
        self.assert_equal(stream.readlines(2), ['34'])
        self.assert_equal(stream.readlines(), ['56\n', 'ab'])

        io = StringIO('123456\nabcdefg')
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readline(100), '123456\n')

        io = StringIO('123456\nabcdefg')
        stream = wsgi.LimitedStream(io, 9)
        self.assert_equal(stream.readlines(100), ['123456\n', 'ab'])

        io = StringIO('123456')
        stream = wsgi.LimitedStream(io, 3)
        self.assert_equal(stream.read(1), '1')
        self.assert_equal(stream.read(1), '2')
        self.assert_equal(stream.read(), '3')
        self.assert_equal(stream.read(), '')

        io = StringIO('123456')
        stream = wsgi.LimitedStream(io, 3)
        self.assert_equal(stream.read(-1), '123')

    def test_limited_stream_disconnection(self):
        io = StringIO('A bit of content')

        # disconnect detection on out of bytes
        stream = wsgi.LimitedStream(io, 255)
        with self.assert_raises(ClientDisconnected):
            stream.read()

        # disconnect detection because file close
        io = StringIO('x' * 255)
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

    def test_get_current_url_unicode(self):
        env = create_environ()
        env['QUERY_STRING'] = 'foo=bar&baz=blah&meh=\xcf'
        rv = wsgi.get_current_url(env)
        self.assertEqual(rv, 'http://localhost/?foo=bar&baz=blah&meh=%CF')

    def test_multi_part_line_breaks(self):
        data = 'abcdef\r\nghijkl\r\nmnopqrstuvwxyz\r\nABCDEFGHIJK'
        test_stream = StringIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=16))
        self.assert_equal(lines, ['abcdef\r\n', 'ghijkl\r\n', 'mnopqrstuvwxyz\r\n', 'ABCDEFGHIJK'])

        data = 'abc\r\nThis line is broken by the buffer length.\r\nFoo bar baz'
        test_stream = StringIO(data)
        lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=24))
        self.assert_equal(lines, ['abc\r\n', 'This line is broken by the buffer length.\r\n', 'Foo bar baz'])

    def test_multi_part_line_breaks_problematic(self):
        data = 'abc\rdef\r\nghi'
        for x in xrange(1, 10):
            test_stream = StringIO(data)
            lines = list(wsgi.make_line_iter(test_stream, limit=len(data), buffer_size=4))
            assert lines == ['abc\r', 'def\r\n', 'ghi']

    def test_iter_functions_support_iterators(self):
        data = ['abcdef\r\nghi', 'jkl\r\nmnopqrstuvwxyz\r', '\nABCDEFGHIJK']
        lines = list(wsgi.make_line_iter(data))
        self.assert_equal(lines, ['abcdef\r\n', 'ghijkl\r\n', 'mnopqrstuvwxyz\r\n', 'ABCDEFGHIJK'])

    def test_make_chunk_iter(self):
        data = ['abcdefXghi', 'jklXmnopqrstuvwxyzX', 'ABCDEFGHIJK']
        rv = list(wsgi.make_chunk_iter(data, 'X'))
        self.assert_equal(rv, ['abcdef', 'ghijkl', 'mnopqrstuvwxyz', 'ABCDEFGHIJK'])

        data = 'abcdefXghijklXmnopqrstuvwxyzXABCDEFGHIJK'
        test_stream = StringIO(data)
        rv = list(wsgi.make_chunk_iter(test_stream, 'X', limit=len(data), buffer_size=4))
        self.assert_equal(rv, ['abcdef', 'ghijkl', 'mnopqrstuvwxyz', 'ABCDEFGHIJK'])

    def test_lines_longer_buffer_size(self):
        data = '1234567890\n1234567890\n'
        for bufsize in xrange(1, 15):
            lines = list(wsgi.make_line_iter(StringIO(data), limit=len(data), buffer_size=4))
            self.assert_equal(lines, ['1234567890\n', '1234567890\n'])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WSGIUtilsTestCase))
    return suite
