# -*- coding: utf-8 -*-
"""
    tests.fixers
    ~~~~~~~~~~~~

    Server / Browser fixers.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

from werkzeug.contrib import fixers
from werkzeug.datastructures import ResponseCacheControl
from werkzeug.http import parse_cache_control_header
from werkzeug.routing import Map, Rule
from werkzeug.test import Client, create_environ
from werkzeug.utils import redirect
from werkzeug.wrappers import Request, Response


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
                 PATH_INFO='/bar'))
        assert response.get_data() == b'PATH_INFO: /bar\nSCRIPT_NAME: '

    def test_cgi_root_fix_custom_app_root(self):
        app = fixers.CGIRootFix(path_check_app, app_root='/baz/')
        response = Response.from_app(
            app,
            dict(create_environ(),
                 SCRIPT_NAME='/foo',
                 PATH_INFO='/bar'))
        assert response.get_data() == b'PATH_INFO: /bar\nSCRIPT_NAME: baz'

    def test_path_info_from_request_uri_fix(self):
        app = fixers.PathInfoFromRequestUriFix(path_check_app)
        for key in 'REQUEST_URI', 'REQUEST_URL', 'UNENCODED_URL':
            env = dict(create_environ(), SCRIPT_NAME='/test', PATH_INFO='/?????')
            env[key] = '/test/foo%25bar?drop=this'
            response = Response.from_app(app, env)
            assert response.get_data() == b'PATH_INFO: /foo%bar\nSCRIPT_NAME: /test'

    @pytest.mark.parametrize(('kwargs', 'base', 'url_root'), (
        pytest.param({}, {
            'REMOTE_ADDR': '192.168.0.2',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.1',
        }, 'http://spam/', id='for'),
        pytest.param({'x_proto': 1}, {
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_PROTO': 'https',
        },  'https://spam/', id='proto'),
        pytest.param({'x_host': 1}, {
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_HOST': 'eggs',
        }, 'http://eggs/', id='host'),
        pytest.param({'x_port': 1}, {
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_PORT': '8080',
        }, 'http://spam:8080/', id='port, host without port'),
        pytest.param({'x_port': 1}, {
            'HTTP_HOST': 'spam:9000',
            'HTTP_X_FORWARDED_PORT': '8080',
        }, 'http://spam:8080/', id='port, host with port'),
        pytest.param({'x_port': 1}, {
            'SERVER_NAME': 'spam',
            'SERVER_PORT': '9000',
            'HTTP_X_FORWARDED_PORT': '8080',
        }, 'http://spam:8080/', id='port, name'),
        pytest.param({'x_prefix': 1}, {
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_PREFIX': '/eggs',
        }, 'http://spam/eggs/', id='prefix'),
        pytest.param({
            'x_for': 1, 'x_proto': 1, 'x_host': 1, 'x_port': 1, 'x_prefix': 1
        }, {
            'REMOTE_ADDR': '192.168.0.2',
            'HTTP_HOST': 'spam:9000',
            'HTTP_X_FORWARDED_FOR': '192.168.0.1',
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_X_FORWARDED_HOST': 'eggs',
            'HTTP_X_FORWARDED_PORT': '443',
            'HTTP_X_FORWARDED_PREFIX': '/ham',
        }, 'https://eggs/ham/', id='all'),
        pytest.param({'x_for': 2}, {
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.1, 192.168.0.2',
        }, 'http://spam/', id='multiple for'),
        pytest.param({'x_for': 0}, {
            'REMOTE_ADDR': '192.168.0.1',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.2',
        }, 'http://spam/', id='ignore 0'),
        pytest.param({'x_for': 3}, {
            'REMOTE_ADDR': '192.168.0.1',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.3, 192.168.0.2',
        }, 'http://spam/', id='ignore len < trusted'),
        pytest.param({}, {
            'REMOTE_ADDR': '192.168.0.2',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.3, 192.168.0.1',
        }, 'http://spam/', id='ignore untrusted'),
        pytest.param({'x_for': 2}, {
            'REMOTE_ADDR': '192.168.0.1',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': ', 192.168.0.3'
        }, 'http://spam/', id='ignore empty'),
        pytest.param({'x_for': 2, 'x_prefix': 1}, {
            'REMOTE_ADDR': '192.168.0.2',
            'HTTP_HOST': 'spam',
            'HTTP_X_FORWARDED_FOR': '192.168.0.1, 192.168.0.3',
            'HTTP_X_FORWARDED_PREFIX': '/ham, /eggs',
        }, 'http://spam/eggs/', id='prefix < for')
    ))
    def test_proxy_fix_new(self, kwargs, base, url_root):
        @Request.application
        def app(request):
            # for header
            assert request.remote_addr == '192.168.0.1'
            # proto, host, port, prefix headers
            assert request.url_root == url_root

            urls = url_map.bind_to_environ(request.environ)
            # build includes prefix
            assert urls.build('parrot') == '/'.join((
                request.script_root, 'parrot'))
            # match doesn't include prefix
            assert urls.match('/parrot')[0] == 'parrot'

            return Response('success')

        url_map = Map([Rule('/parrot', endpoint='parrot')])
        app = fixers.ProxyFix(app, **kwargs)

        base.setdefault('REMOTE_ADDR', '192.168.0.1')
        environ = create_environ(environ_overrides=base)
        # host is always added, remove it if the test doesn't set it
        if 'HTTP_HOST' not in base:
            del environ['HTTP_HOST']

        # ensure app request has correct headers
        response = Response.from_app(app, environ)
        assert response.get_data() == b'success'

        # ensure redirect location is correct
        redirect_app = redirect(
            url_map.bind_to_environ(environ).build('parrot'))
        response = Response.from_app(redirect_app, environ)
        location = response.headers['Location']
        assert location == url_root + 'parrot'

    def test_proxy_fix_deprecations(self):
        app = pytest.deprecated_call(fixers.ProxyFix, None, 2)
        assert app.x_for == 2

        with pytest.deprecated_call():
            assert app.num_proxies == 2

        with pytest.deprecated_call():
            assert app.get_remote_addr(['spam', 'eggs']) == 'spam'

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
