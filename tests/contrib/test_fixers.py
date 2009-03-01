from nose.tools import assert_raises
from werkzeug import Request, Response, create_environ
from werkzeug.contrib import fixers


@Request.application
def path_check_app(request):
    return Response('PATH_INFO: %s\nSCRIPT_NAME: %s' % (
        request.environ.get('PATH_INFO', ''),
        request.environ.get('SCRIPT_NAME', '')
    ))


def test_lighttpd_cgi_root_fix():
    """Test the LighttpdCGIRootFix fixer"""
    app = fixers.LighttpdCGIRootFix(path_check_app)
    response = Response.from_app(app, dict(create_environ(),
        SCRIPT_NAME='/foo',
        PATH_INFO='/bar'
    ))
    assert response.data == 'PATH_INFO: /foo/bar\nSCRIPT_NAME: '


def test_path_info_from_request_uri_fix():
    """Test the PathInfoFromRequestUriFix fixer"""
    app = fixers.PathInfoFromRequestUriFix(path_check_app)
    for key in 'REQUEST_URI', 'REQUEST_URL', 'UNENCODED_URL':
        env = dict(create_environ(), SCRIPT_NAME='/test', PATH_INFO='/?????')
        env[key] = '/test/foo%25bar?drop=this'
        response = Response.from_app(app, env)
        assert response.data == 'PATH_INFO: /foo%bar\nSCRIPT_NAME: /test'


def test_proxy_fix():
    """Test the ProxyFix fixer"""
    @fixers.ProxyFix
    @Request.application
    def app(request):
        return Response('%s|%s' % (
            request.remote_addr,
            # do not use request.host as this fixes too :)
            request.environ['HTTP_HOST']
        ))
    response = Response.from_app(app, dict(create_environ(),
        HTTP_X_FORWARDED_HOST='example.com',
        HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8',
        REMOTE_ADDR='127.0.0.1',
        HTTP_HOST='fake'
    ))
    assert response.data == '1.2.3.4|example.com'


def test_header_rewriter_fix():
    """Test the HeaderRewriterFix fixer"""
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
