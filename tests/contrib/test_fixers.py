# -*- coding: utf-8 -*-
"""
    tests.fixers
    ~~~~~~~~~~~~

    Server / Browser fixers.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

from tests import strict_eq
from werkzeug._compat import to_bytes
from werkzeug.datastructures import ResponseCacheControl
from werkzeug.http import parse_cache_control_header

from werkzeug.test import create_environ, Client
from werkzeug.wrappers import Request, Response
from werkzeug.contrib import fixers
from werkzeug.utils import redirect
from werkzeug.wsgi import get_host


@Request.application
def path_check_app(request):
    return Response('PATH_INFO: %s\nSCRIPT_NAME: %s' % (
        request.environ.get('PATH_INFO', ''),
        request.environ.get('SCRIPT_NAME', '')
    ))


class TestServerFixer(object):

    def test_cgi_root_fix(self):
        app = fixers.CGIRootFix(path_check_app)
        response = Response.from_app(
            app,
            dict(create_environ(),
                 SCRIPT_NAME='/foo',
                 PATH_INFO='/bar',
                 SERVER_SOFTWARE='lighttpd/1.4.27'))
        assert response.get_data() == b'PATH_INFO: /foo/bar\nSCRIPT_NAME: '

    def test_cgi_root_fix_custom_app_root(self):
        app = fixers.CGIRootFix(path_check_app, app_root='/baz/poop/')
        response = Response.from_app(
            app,
            dict(create_environ(),
                 SCRIPT_NAME='/foo',
                 PATH_INFO='/bar'))
        assert response.get_data() == b'PATH_INFO: /foo/bar\nSCRIPT_NAME: baz/poop'

    def test_path_info_from_request_uri_fix(self):
        app = fixers.PathInfoFromRequestUriFix(path_check_app)
        for key in 'REQUEST_URI', 'REQUEST_URL', 'UNENCODED_URL':
            env = dict(create_environ(), SCRIPT_NAME='/test', PATH_INFO='/?????')
            env[key] = '/test/foo%25bar?drop=this'
            response = Response.from_app(app, env)
            assert response.get_data() == b'PATH_INFO: /foo%bar\nSCRIPT_NAME: /test'

    @pytest.mark.parametrize('environ,assumed_addr,assumed_host', [
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1'
        }, '127.0.0.1', 'http://internal', id='No proxy, with Host'),
        pytest.param({
            'SERVER_NAME': 'internal',
            'SERVER_PORT': '80',
            'REMOTE_ADDR': '127.0.0.1'
        }, '127.0.0.1', 'http://internal', id='No proxy, no Host'),
        pytest.param({
            'HTTP_HOST': 'internal:80',
            'REMOTE_ADDR': '127.0.0.1'
        }, '127.0.0.1', 'http://internal', id='Sanitize HTTP port'),
        pytest.param({
            'wsgi.url_scheme': 'https',
            'HTTP_HOST': 'internal:443',
            'REMOTE_ADDR': '127.0.0.1'
        }, '127.0.0.1', 'https://internal', id='Sanitize HTTPS port'),
        pytest.param({
            'HTTP_HOST': 'internal:8080',
            'REMOTE_ADDR': '127.0.0.1'
        }, '127.0.0.1', 'http://internal:8080', id='Custom port'),
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_FOR': '1.2.3.4, 5.6.7.8'
        }, '1.2.3.4', 'http://internal', id='X-Forwarded-For'),
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_X_FORWARDED_HOST': 'example.com',
            'HTTP_X_FORWARDED_PORT': '8443',
        }, '127.0.0.1', 'https://example.com:8443', id='X-Forwarded-*'),
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_PORT': '8080',
        }, '127.0.0.1', 'http://internal:8080', id='HTTP X-Port, no X-Host'),
        pytest.param({
            'SERVER_NAME': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_PORT': '8080',
        }, '127.0.0.1', 'http://internal:8080', id='HTTP X-Port, no Host'),
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_X_FORWARDED_PORT': '8443',
        }, '127.0.0.1', 'https://internal:8443', id='HTTPS X-Port, no X-Host'),
        pytest.param({
            'HTTP_HOST': 'internal',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_X_FORWARDED_HOST': 'example.com',
            'HTTP_X_FORWARDED_PORT': '443',
            'HTTP_X_FORWARDED_FOR': '1.2.3.4, 5.6.7.8'
        }, '1.2.3.4', 'https://example.com', id='All together'),
    ])
    def test_proxy_fix(self, environ, assumed_addr, assumed_host):
        @Request.application
        def app(request):
            return Response('%s|%s' % (
                request.remote_addr,
                # do not use request.host as this fixes too :)
                request.environ['wsgi.url_scheme'] + '://' +
                get_host(request.environ)
            ))
        app = fixers.ProxyFix(app, num_proxies=2)
        has_host = 'HTTP_HOST' in environ
        environ = dict(
            create_environ(),
            **environ
        )
        if not has_host:
            del environ['HTTP_HOST']  # create_environ() defaults to 'localhost'

        response = Response.from_app(app, environ)

        assert response.get_data() == to_bytes('{}|{}'.format(
            assumed_addr, assumed_host))

        # And we must check that if it is a redirection it is
        # correctly done:

        redirect_app = redirect('/foo/bar.hml')
        response = Response.from_app(redirect_app, environ)

        wsgi_headers = response.get_wsgi_headers(environ)
        assert wsgi_headers['Location'] == '{}/foo/bar.hml'.format(
            assumed_host)

    def test_proxy_fix_forwarded_prefix(self):
        @fixers.ProxyFix
        @Request.application
        def app(request):
            return Response('%s' % (
                request.script_root
            ))
        environ = dict(
            create_environ(),
            HTTP_X_FORWARDED_PREFIX="/foo/bar",
        )

        response = Response.from_app(app, environ)
        assert response.get_data() == b'/foo/bar'

    def test_proxy_fix_weird_enum(self):
        @fixers.ProxyFix
        @Request.application
        def app(request):
            return Response(request.remote_addr)
        environ = dict(
            create_environ(),
            HTTP_X_FORWARDED_FOR=',',
            REMOTE_ADDR='127.0.0.1',
        )

        response = Response.from_app(app, environ)
        strict_eq(response.get_data(), b'127.0.0.1')

    def test_header_rewriter_fix(self):
        @Request.application
        def application(request):
            return Response("", headers=[
                ('X-Foo', 'bar')
            ])
        application = fixers.HeaderRewriterFix(application, ('X-Foo',), (('X-Bar', '42'),))
        response = Response.from_app(application, create_environ())
        assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
        assert 'X-Foo' not in response.headers
        assert response.headers['X-Bar'] == '42'


class TestBrowserFixer(object):

    def test_ie_fixes(self):
        @fixers.InternetExplorerFix
        @Request.application
        def application(request):
            response = Response('binary data here', mimetype='application/vnd.ms-excel')
            response.headers['Vary'] = 'Cookie'
            response.headers['Content-Disposition'] = 'attachment; filename=foo.xls'
            return response

        c = Client(application, Response)
        response = c.get('/', headers=[
            ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)')
        ])

        # IE gets no vary
        assert response.get_data() == b'binary data here'
        assert 'vary' not in response.headers
        assert response.headers['content-disposition'] == 'attachment; filename=foo.xls'
        assert response.headers['content-type'] == 'application/vnd.ms-excel'

        # other browsers do
        c = Client(application, Response)
        response = c.get('/')
        assert response.get_data() == b'binary data here'
        assert 'vary' in response.headers

        cc = ResponseCacheControl()
        cc.no_cache = True

        @fixers.InternetExplorerFix
        @Request.application
        def application(request):
            response = Response('binary data here', mimetype='application/vnd.ms-excel')
            response.headers['Pragma'] = ', '.join(pragma)
            response.headers['Cache-Control'] = cc.to_header()
            response.headers['Content-Disposition'] = 'attachment; filename=foo.xls'
            return response

        # IE has no pragma or cache control
        pragma = ('no-cache',)
        c = Client(application, Response)
        response = c.get('/', headers=[
            ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)')
        ])
        assert response.get_data() == b'binary data here'
        assert 'pragma' not in response.headers
        assert 'cache-control' not in response.headers
        assert response.headers['content-disposition'] == 'attachment; filename=foo.xls'

        # IE has simplified pragma
        pragma = ('no-cache', 'x-foo')
        cc.proxy_revalidate = True
        response = c.get('/', headers=[
            ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)')
        ])
        assert response.get_data() == b'binary data here'
        assert response.headers['pragma'] == 'x-foo'
        assert response.headers['cache-control'] == 'proxy-revalidate'
        assert response.headers['content-disposition'] == 'attachment; filename=foo.xls'

        # regular browsers get everything
        response = c.get('/')
        assert response.get_data() == b'binary data here'
        assert response.headers['pragma'] == 'no-cache, x-foo'
        cc = parse_cache_control_header(response.headers['cache-control'],
                                        cls=ResponseCacheControl)
        assert cc.no_cache
        assert cc.proxy_revalidate
        assert response.headers['content-disposition'] == 'attachment; filename=foo.xls'
