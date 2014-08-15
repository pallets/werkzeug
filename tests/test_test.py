# -*- coding: utf-8 -*-
"""
    tests.test
    ~~~~~~~~~~

    Tests the testing tools.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement

import pytest

import sys
from io import BytesIO
from werkzeug._compat import iteritems, to_bytes

from tests import WerkzeugTests, strict_eq

from werkzeug.wrappers import Request, Response, BaseResponse
from werkzeug.test import Client, EnvironBuilder, create_environ, \
    ClientRedirectError, stream_encode_multipart, run_wsgi_app
from werkzeug.utils import redirect
from werkzeug.formparser import parse_form_data
from werkzeug.datastructures import MultiDict, FileStorage


def cookie_app(environ, start_response):
    """A WSGI application which sets a cookie, and returns as a ersponse any
    cookie which exists.
    """
    response = Response(environ.get('HTTP_COOKIE', 'No Cookie'),
                        mimetype='text/plain')
    response.set_cookie('test', 'test')
    return response(environ, start_response)


def redirect_loop_app(environ, start_response):
    response = redirect('http://localhost/some/redirect/')
    return response(environ, start_response)


def redirect_with_get_app(environ, start_response):
    req = Request(environ)
    if req.url not in ('http://localhost/',
                       'http://localhost/first/request',
                       'http://localhost/some/redirect/'):
        assert False, 'redirect_demo_app() did not expect URL "%s"' % req.url
    if '/some/redirect' not in req.url:
        response = redirect('http://localhost/some/redirect/')
    else:
        response = Response('current url: %s' % req.url)
    return response(environ, start_response)


def redirect_with_post_app(environ, start_response):
    req = Request(environ)
    if req.url == 'http://localhost/some/redirect/':
        assert req.method == 'GET', 'request should be GET'
        assert not req.form, 'request should not have data'
        response = Response('current url: %s' % req.url)
    else:
        response = redirect('http://localhost/some/redirect/')
    return response(environ, start_response)


def external_redirect_demo_app(environ, start_response):
    response = redirect('http://example.com/')
    return response(environ, start_response)


def external_subdomain_redirect_demo_app(environ, start_response):
    if 'test.example.com' in environ['HTTP_HOST']:
        response = Response('redirected successfully to subdomain')
    else:
        response = redirect('http://test.example.com/login')
    return response(environ, start_response)


def multi_value_post_app(environ, start_response):
    req = Request(environ)
    assert req.form['field'] == 'val1', req.form['field']
    assert req.form.getlist('field') == ['val1', 'val2'], req.form.getlist('field')
    response = Response('ok')
    return response(environ, start_response)


class TestTest(WerkzeugTests):

    def test_cookie_forging(self):
        c = Client(cookie_app)
        c.set_cookie('localhost', 'foo', 'bar')
        appiter, code, headers = c.open()
        strict_eq(list(appiter), [b'foo=bar'])

    def test_set_cookie_app(self):
        c = Client(cookie_app)
        appiter, code, headers = c.open()
        assert 'Set-Cookie' in dict(headers)

    def test_cookiejar_stores_cookie(self):
        c = Client(cookie_app)
        appiter, code, headers = c.open()
        assert 'test' in c.cookie_jar._cookies['localhost.local']['/']

    def test_no_initial_cookie(self):
        c = Client(cookie_app)
        appiter, code, headers = c.open()
        strict_eq(b''.join(appiter), b'No Cookie')

    def test_resent_cookie(self):
        c = Client(cookie_app)
        c.open()
        appiter, code, headers = c.open()
        strict_eq(b''.join(appiter), b'test=test')

    def test_disable_cookies(self):
        c = Client(cookie_app, use_cookies=False)
        c.open()
        appiter, code, headers = c.open()
        strict_eq(b''.join(appiter), b'No Cookie')

    def test_cookie_for_different_path(self):
        c = Client(cookie_app)
        c.open('/path1')
        appiter, code, headers = c.open('/path2')
        strict_eq(b''.join(appiter), b'test=test')

    def test_environ_builder_basics(self):
        b = EnvironBuilder()
        assert b.content_type is None
        b.method = 'POST'
        assert b.content_type == 'application/x-www-form-urlencoded'
        b.files.add_file('test', BytesIO(b'test contents'), 'test.txt')
        assert b.files['test'].content_type == 'text/plain'
        assert b.content_type == 'multipart/form-data'
        b.form['test'] = 'normal value'

        req = b.get_request()
        b.close()

        strict_eq(req.url, u'http://localhost/')
        strict_eq(req.method, 'POST')
        strict_eq(req.form['test'], u'normal value')
        assert req.files['test'].content_type == 'text/plain'
        strict_eq(req.files['test'].filename, u'test.txt')
        strict_eq(req.files['test'].read(), b'test contents')

    def test_environ_builder_headers(self):
        b = EnvironBuilder(environ_base={'HTTP_USER_AGENT': 'Foo/0.1'},
                           environ_overrides={'wsgi.version': (1, 1)})
        b.headers['X-Beat-My-Horse'] = 'very well sir'
        env = b.get_environ()
        strict_eq(env['HTTP_USER_AGENT'], 'Foo/0.1')
        strict_eq(env['HTTP_X_BEAT_MY_HORSE'], 'very well sir')
        strict_eq(env['wsgi.version'], (1, 1))

        b.headers['User-Agent'] = 'Bar/1.0'
        env = b.get_environ()
        strict_eq(env['HTTP_USER_AGENT'], 'Bar/1.0')

    def test_environ_builder_headers_content_type(self):
        b = EnvironBuilder(headers={'Content-Type': 'text/plain'})
        env = b.get_environ()
        assert env['CONTENT_TYPE'] == 'text/plain'
        b = EnvironBuilder(content_type='text/html',
                           headers={'Content-Type': 'text/plain'})
        env = b.get_environ()
        assert env['CONTENT_TYPE'] == 'text/html'

    def test_environ_builder_paths(self):
        b = EnvironBuilder(path='/foo', base_url='http://example.com/')
        strict_eq(b.base_url, 'http://example.com/')
        strict_eq(b.path, '/foo')
        strict_eq(b.script_root, '')
        strict_eq(b.host, 'example.com')

        b = EnvironBuilder(path='/foo', base_url='http://example.com/bar')
        strict_eq(b.base_url, 'http://example.com/bar/')
        strict_eq(b.path, '/foo')
        strict_eq(b.script_root, '/bar')
        strict_eq(b.host, 'example.com')

        b.host = 'localhost'
        strict_eq(b.base_url, 'http://localhost/bar/')
        b.base_url = 'http://localhost:8080/'
        strict_eq(b.host, 'localhost:8080')
        strict_eq(b.server_name, 'localhost')
        strict_eq(b.server_port, 8080)

        b.host = 'foo.invalid'
        b.url_scheme = 'https'
        b.script_root = '/test'
        env = b.get_environ()
        strict_eq(env['SERVER_NAME'], 'foo.invalid')
        strict_eq(env['SERVER_PORT'], '443')
        strict_eq(env['SCRIPT_NAME'], '/test')
        strict_eq(env['PATH_INFO'], '/foo')
        strict_eq(env['HTTP_HOST'], 'foo.invalid')
        strict_eq(env['wsgi.url_scheme'], 'https')
        strict_eq(b.base_url, 'https://foo.invalid/test/')

    def test_environ_builder_content_type(self):
        builder = EnvironBuilder()
        assert builder.content_type is None
        builder.method = 'POST'
        assert builder.content_type == 'application/x-www-form-urlencoded'
        builder.form['foo'] = 'bar'
        assert builder.content_type == 'application/x-www-form-urlencoded'
        builder.files.add_file('blafasel', BytesIO(b'foo'), 'test.txt')
        assert builder.content_type == 'multipart/form-data'
        req = builder.get_request()
        strict_eq(req.form['foo'], u'bar')
        strict_eq(req.files['blafasel'].read(), b'foo')

    def test_environ_builder_stream_switch(self):
        d = MultiDict(dict(foo=u'bar', blub=u'blah', hu=u'hum'))
        for use_tempfile in False, True:
            stream, length, boundary = stream_encode_multipart(
                d, use_tempfile, threshold=150)
            assert isinstance(stream, BytesIO) != use_tempfile

            form = parse_form_data({'wsgi.input': stream, 'CONTENT_LENGTH': str(length),
                                    'CONTENT_TYPE': 'multipart/form-data; boundary="%s"' %
                                    boundary})[1]
            strict_eq(form, d)
            stream.close()

    def test_environ_builder_unicode_file_mix(self):
        for use_tempfile in False, True:
            f = FileStorage(BytesIO(u'\N{SNOWMAN}'.encode('utf-8')),
                            'snowman.txt')
            d = MultiDict(dict(f=f, s=u'\N{SNOWMAN}'))
            stream, length, boundary = stream_encode_multipart(
                d, use_tempfile, threshold=150)
            assert isinstance(stream, BytesIO) != use_tempfile

            _, form, files = parse_form_data({
                'wsgi.input': stream,
                'CONTENT_LENGTH': str(length),
                'CONTENT_TYPE': 'multipart/form-data; boundary="%s"' %
                                    boundary
            })
            strict_eq(form['s'], u'\N{SNOWMAN}')
            strict_eq(files['f'].name, 'f')
            strict_eq(files['f'].filename, u'snowman.txt')
            strict_eq(files['f'].read(),
                                     u'\N{SNOWMAN}'.encode('utf-8'))
            stream.close()

    def test_create_environ(self):
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
        for key, value in iteritems(expected):
            assert env[key] == value
        strict_eq(env['wsgi.input'].read(0), b'')
        strict_eq(create_environ('/foo', 'http://example.com/')['SCRIPT_NAME'], '')

    def test_file_closing(self):
        closed = []
        class SpecialInput(object):
            def read(self):
                return ''
            def close(self):
                closed.append(self)

        env = create_environ(data={'foo': SpecialInput()})
        strict_eq(len(closed), 1)
        builder = EnvironBuilder()
        builder.files.add_file('blah', SpecialInput())
        builder.close()
        strict_eq(len(closed), 2)

    def test_follow_redirect(self):
        env = create_environ('/', base_url='http://localhost')
        c = Client(redirect_with_get_app)
        appiter, code, headers = c.open(environ_overrides=env, follow_redirects=True)
        strict_eq(code, '200 OK')
        strict_eq(b''.join(appiter), b'current url: http://localhost/some/redirect/')

        # Test that the :cls:`Client` is aware of user defined response wrappers
        c = Client(redirect_with_get_app, response_wrapper=BaseResponse)
        resp = c.get('/', follow_redirects=True)
        strict_eq(resp.status_code, 200)
        strict_eq(resp.data, b'current url: http://localhost/some/redirect/')

        # test with URL other than '/' to make sure redirected URL's are correct
        c = Client(redirect_with_get_app, response_wrapper=BaseResponse)
        resp = c.get('/first/request', follow_redirects=True)
        strict_eq(resp.status_code, 200)
        strict_eq(resp.data, b'current url: http://localhost/some/redirect/')

    def test_follow_external_redirect(self):
        env = create_environ('/', base_url='http://localhost')
        c = Client(external_redirect_demo_app)
        pytest.raises(RuntimeError, lambda:
            c.get(environ_overrides=env, follow_redirects=True))

    def test_follow_external_redirect_on_same_subdomain(self):
        env = create_environ('/', base_url='http://example.com')
        c = Client(external_subdomain_redirect_demo_app, allow_subdomain_redirects=True)
        c.get(environ_overrides=env, follow_redirects=True)

        # check that this does not work for real external domains
        env = create_environ('/', base_url='http://localhost')
        pytest.raises(RuntimeError, lambda:
            c.get(environ_overrides=env, follow_redirects=True))

        # check that subdomain redirects fail if no `allow_subdomain_redirects` is applied
        c = Client(external_subdomain_redirect_demo_app)
        pytest.raises(RuntimeError, lambda:
            c.get(environ_overrides=env, follow_redirects=True))

    def test_follow_redirect_loop(self):
        c = Client(redirect_loop_app, response_wrapper=BaseResponse)
        with pytest.raises(ClientRedirectError):
            resp = c.get('/', follow_redirects=True)

    def test_follow_redirect_with_post(self):
        c = Client(redirect_with_post_app, response_wrapper=BaseResponse)
        resp = c.post('/', follow_redirects=True, data='foo=blub+hehe&blah=42')
        strict_eq(resp.status_code, 200)
        strict_eq(resp.data, b'current url: http://localhost/some/redirect/')

    def test_path_info_script_name_unquoting(self):
        def test_app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [environ['PATH_INFO'] + '\n' + environ['SCRIPT_NAME']]
        c = Client(test_app, response_wrapper=BaseResponse)
        resp = c.get('/foo%40bar')
        strict_eq(resp.data, b'/foo@bar\n')
        c = Client(test_app, response_wrapper=BaseResponse)
        resp = c.get('/foo%40bar', 'http://localhost/bar%40baz')
        strict_eq(resp.data, b'/foo@bar\n/bar@baz')

    def test_multi_value_submit(self):
        c = Client(multi_value_post_app, response_wrapper=BaseResponse)
        data = {
            'field': ['val1','val2']
        }
        resp = c.post('/', data=data)
        strict_eq(resp.status_code, 200)
        c = Client(multi_value_post_app, response_wrapper=BaseResponse)
        data = MultiDict({
            'field': ['val1', 'val2']
        })
        resp = c.post('/', data=data)
        strict_eq(resp.status_code, 200)

    def test_iri_support(self):
        b = EnvironBuilder(u'/föö-bar', base_url=u'http://☃.net/')
        strict_eq(b.path, '/f%C3%B6%C3%B6-bar')
        strict_eq(b.base_url, 'http://xn--n3h.net/')

    def test_run_wsgi_apps(self):
        def simple_app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['Hello World!']
        app_iter, status, headers = run_wsgi_app(simple_app, {})
        strict_eq(status, '200 OK')
        strict_eq(list(headers), [('Content-Type', 'text/html')])
        strict_eq(app_iter, ['Hello World!'])

        def yielding_app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            yield 'Hello '
            yield 'World!'
        app_iter, status, headers = run_wsgi_app(yielding_app, {})
        strict_eq(status, '200 OK')
        strict_eq(list(headers), [('Content-Type', 'text/html')])
        strict_eq(list(app_iter), ['Hello ', 'World!'])

    def test_multiple_cookies(self):
        @Request.application
        def test_app(request):
            response = Response(repr(sorted(request.cookies.items())))
            response.set_cookie(u'test1', b'foo')
            response.set_cookie(u'test2', b'bar')
            return response
        client = Client(test_app, Response)
        resp = client.get('/')
        strict_eq(resp.data, b'[]')
        resp = client.get('/')
        strict_eq(resp.data,
                          to_bytes(repr([('test1', u'foo'), ('test2', u'bar')]), 'ascii'))

    def test_correct_open_invocation_on_redirect(self):
        class MyClient(Client):
            counter = 0
            def open(self, *args, **kwargs):
                self.counter += 1
                env = kwargs.setdefault('environ_overrides', {})
                env['werkzeug._foo'] = self.counter
                return Client.open(self, *args, **kwargs)

        @Request.application
        def test_app(request):
            return Response(str(request.environ['werkzeug._foo']))

        c = MyClient(test_app, response_wrapper=Response)
        strict_eq(c.get('/').data, b'1')
        strict_eq(c.get('/').data, b'2')
        strict_eq(c.get('/').data, b'3')

    def test_correct_encoding(self):
        req = Request.from_values(u'/\N{SNOWMAN}', u'http://example.com/foo')
        strict_eq(req.script_root, u'/foo')
        strict_eq(req.path, u'/\N{SNOWMAN}')

    def test_full_url_requests_with_args(self):
        base = 'http://example.com/'

        @Request.application
        def test_app(request):
            return Response(request.args['x'])
        client = Client(test_app, Response)
        resp = client.get('/?x=42', base)
        strict_eq(resp.data, b'42')
        resp = client.get('http://www.example.com/?x=23', base)
        strict_eq(resp.data, b'23')
