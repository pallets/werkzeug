# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers test
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import pickle
from StringIO import StringIO

from nose.tools import assert_raises

from datetime import datetime, timedelta
from werkzeug.wrappers import *
from werkzeug.wsgi import LimitedStream
from werkzeug.http import generate_etag
from werkzeug.datastructures import MultiDict, ImmutableOrderedMultiDict, \
     ImmutableList, ImmutableTypeConversionDict
from werkzeug.test import Client, create_environ, run_wsgi_app


class RequestTestResponse(BaseResponse):
    """Subclass of the normal response class we use to test response
    and base classes.  Has some methods to test if things in the
    response match.
    """

    def __init__(self, response, status, headers):
        BaseResponse.__init__(self, response, status, headers)
        self.body_data = pickle.loads(self.data)

    def __getitem__(self, key):
        return self.body_data[key]


def request_demo_app(environ, start_response):
    request = BaseRequest(environ)
    assert 'werkzeug.request' in environ
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [pickle.dumps({
        'args':             request.args,
        'args_as_list':     request.args.lists(),
        'form':             request.form,
        'form_as_list':     request.form.lists(),
        'environ':          prepare_environ_pickle(request.environ),
        'data':             request.data
    })]


def prepare_environ_pickle(environ):
    result = {}
    for key, value in environ.iteritems():
        try:
            pickle.dumps((key, value))
        except:
            continue
        result[key] = value
    return result


def assert_environ(environ, method):
    assert environ['REQUEST_METHOD'] == method
    assert environ['PATH_INFO'] == '/'
    assert environ['SCRIPT_NAME'] == ''
    assert environ['SERVER_NAME'] == 'localhost'
    assert environ['wsgi.version'] == (1, 0)
    assert environ['wsgi.url_scheme'] == 'http'


def test_base_request():
    """Base request behavior"""
    client = Client(request_demo_app, RequestTestResponse)

    # get requests
    response = client.get('/?foo=bar&foo=hehe')
    assert response['args'] == MultiDict([('foo', 'bar'), ('foo', 'hehe')])
    assert response['args_as_list'] == [('foo', ['bar', 'hehe'])]
    assert response['form'] == MultiDict()
    assert response['form_as_list'] == []
    assert response['data'] == ''
    assert_environ(response['environ'], 'GET')

    # post requests with form data
    response = client.post('/?blub=blah', data='foo=blub+hehe&blah=42',
                           content_type='application/x-www-form-urlencoded')
    assert response['args'] == MultiDict([('blub', 'blah')])
    assert response['args_as_list'] == [('blub', ['blah'])]
    assert response['form'] == MultiDict([('foo', 'blub hehe'), ('blah', '42')])
    assert response['data'] == ''
    # currently we do not guarantee that the values are ordered correctly
    # for post data.
    ## assert response['form_as_list'] == [('foo', ['blub hehe']), ('blah', ['42'])]
    assert_environ(response['environ'], 'POST')

    # post requests with json data
    json = '{"foo": "bar", "blub": "blah"}'
    response = client.post('/?a=b', data=json, content_type='application/json')
    assert response['data'] == json
    assert response['args'] == MultiDict([('a', 'b')])
    assert response['form'] == MultiDict()


def test_access_route():
    """Check access route on the wrappers"""
    req = Request.from_values(headers={
        'X-Forwarded-For': '192.168.1.2, 192.168.1.1'
    })
    req.environ['REMOTE_ADDR'] = '192.168.1.3'
    req.is_behind_proxy = True
    assert req.access_route == ['192.168.1.2', '192.168.1.1']
    assert req.remote_addr == '192.168.1.2'
    req.is_behind_proxy = False
    assert req.access_route == ['192.168.1.2', '192.168.1.1']
    assert req.remote_addr == '192.168.1.3'

    req = Request.from_values()
    req.environ['REMOTE_ADDR'] = '192.168.1.3'
    assert req.access_route == ['192.168.1.3']


def test_url_request_descriptors():
    """Basic URL request descriptors"""
    req = Request.from_values('/bar?foo=baz', 'http://example.com/test')
    assert req.path == u'/bar'
    assert req.script_root == u'/test'
    assert req.url == 'http://example.com/test/bar?foo=baz'
    assert req.base_url == 'http://example.com/test/bar'
    assert req.url_root == 'http://example.com/test/'
    assert req.host_url == 'http://example.com/'
    assert req.host == 'example.com'


def test_authorization_mixin():
    """Authorization mixin"""
    request = Request.from_values(headers={
        'Authorization': 'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=='
    })
    a = request.authorization
    assert a.type == 'basic'
    assert a.username == 'Aladdin'
    assert a.password == 'open sesame'


def test_base_response():
    """Base respone behavior"""
    # unicode
    response = BaseResponse(u'öäü')
    assert response.data == 'öäü'

    # writing
    response = Response('foo')
    response.stream.write('bar')
    assert response.data == 'foobar'

    # set cookie
    response = BaseResponse()
    response.set_cookie('foo', 'bar', 60, 0, '/blub', 'example.org', False)
    assert response.headers.to_list() == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Set-Cookie', 'foo=bar; Domain=example.org; expires=Thu, '
         '01-Jan-1970 00:00:00 GMT; Max-Age=60; Path=/blub')
    ]

    # delete cookie
    response = BaseResponse()
    response.delete_cookie('foo')
    assert response.headers.to_list() == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Set-Cookie', 'foo=; expires=Thu, 01-Jan-1970 00:00:00 GMT; Max-Age=0; Path=/')
    ]

    # close call forwarding
    closed = []
    class Iterable(object):
        def next(self):
            raise StopIteration()
        def __iter__(self):
            return self
        def close(self):
            closed.append(True)
    response = BaseResponse(Iterable())
    response.call_on_close(lambda: closed.append(True))
    app_iter, status, headers = run_wsgi_app(response,
                                             create_environ(),
                                             buffered=True)
    assert status == '200 OK'
    assert ''.join(app_iter) == ''
    assert len(closed) == 2


def test_response_status_codes():
    """Response status codes"""
    response = BaseResponse()
    response.status_code = 404
    assert response.status == '404 NOT FOUND'
    response.status = '200 OK'
    assert response.status_code == 200
    response.status = '999 WTF'
    assert response.status_code == 999
    response.status_code = 588
    assert response.status_code == 588
    assert response.status == '588 UNKNOWN'
    response.status = 'wtf'
    assert response.status_code == 0


def test_type_forcing():
    """Response Type forcing"""
    def wsgi_application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return ['Hello World!']
    base_response = BaseResponse('Hello World!', content_type='text/html')

    class SpecialResponse(Response):
        def foo(self):
            return 42

    # good enough for this simple application, but don't ever use that in
    # real world examples!
    fake_env = {}

    for orig_resp in wsgi_application, base_response:
        response = SpecialResponse.force_type(orig_resp, fake_env)
        assert response.__class__ is SpecialResponse
        assert response.foo() == 42
        assert response.data == 'Hello World!'
        assert response.content_type == 'text/html'

    # without env, no arbitrary conversion
    assert_raises(TypeError, SpecialResponse.force_type, wsgi_application)


def test_accept_mixin():
    """Accept request-wrapper mixin"""
    request = Request({
        'HTTP_ACCEPT':  'text/xml,application/xml,application/xhtml+xml,'
                        'text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
        'HTTP_ACCEPT_CHARSET': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
        'HTTP_ACCEPT_ENCODING': 'gzip,deflate',
        'HTTP_ACCEPT_LANGUAGE': 'en-us,en;q=0.5'
    })
    assert request.accept_mimetypes == CharsetAccept([
        ('text/xml', 1), ('image/png', 1), ('application/xml', 1),
        ('application/xhtml+xml', 1), ('text/html', 0.9),
        ('text/plain', 0.8), ('*/*', 0.5)
    ])
    assert request.accept_charsets == CharsetAccept([
        ('ISO-8859-1', 1), ('utf-8', 0.7), ('*', 0.7)
    ])
    assert request.accept_encodings == CharsetAccept([('gzip', 1), ('deflate', 1)])
    assert request.accept_languages == CharsetAccept([('en-us', 1), ('en', 0.5)])

    request = Request({'HTTP_ACCEPT': ''})
    assert request.accept_mimetypes == CharsetAccept()


def test_etag_request_mixin():
    """ETag request-wrapper mixin"""
    request = Request({
        'HTTP_CACHE_CONTROL':       'no-store, no-cache',
        'HTTP_IF_MATCH':            'w/"foo", bar, "baz"',
        'HTTP_IF_NONE_MATCH':       'w/"foo", bar, "baz"',
        'HTTP_IF_MODIFIED_SINCE':   'Tue, 22 Jan 2008 11:18:44 GMT',
        'HTTP_IF_UNMODIFIED_SINCE': 'Tue, 22 Jan 2008 11:18:44 GMT'
    })
    assert request.cache_control.no_store
    assert request.cache_control.no_cache

    for etags in request.if_match, request.if_none_match:
        assert etags('bar')
        assert etags.contains_raw('w/"foo"')
        assert etags.contains_weak('foo')
        assert not etags.contains('foo')

    assert request.if_modified_since == datetime(2008, 1, 22, 11, 18, 44)
    assert request.if_unmodified_since == datetime(2008, 1, 22, 11, 18, 44)


def test_user_agent_mixin():
    """User agent request-wrapper mixin"""
    user_agents = [
        ('Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US; rv:1.8.1.11) '
         'Gecko/20071127 Firefox/2.0.0.11', 'firefox', 'macos', '2.0.0.11',
         'en-US'),
        ('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; de-DE) Opera 8.54',
         'opera', 'windows', '8.54', 'de-DE'),
        ('Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420 '
         '(KHTML, like Gecko) Version/3.0 Mobile/1A543a Safari/419.3',
         'safari', 'iphone', '419.3', 'en'),
        ('Bot Googlebot/2.1 ( http://www.googlebot.com/bot.html)',
         'google', None, '2.1', None)
    ]
    for ua, browser, platform, version, lang in user_agents:
        print locals()
        request = Request({'HTTP_USER_AGENT': ua})
        assert request.user_agent.browser == browser
        assert request.user_agent.platform == platform
        assert request.user_agent.version == version
        assert request.user_agent.language == lang
        assert bool(request.user_agent)
        assert request.user_agent.to_header() == ua
        assert str(request.user_agent) == ua

    request = Request({'HTTP_USER_AGENT': 'foo'})
    assert not request.user_agent


def test_etag_response_mixin():
    """ETag response-wrapper mixin"""
    response = Response('Hello World')
    assert response.get_etag() == (None, None)
    response.add_etag()
    assert response.get_etag() == ('b10a8db164e0754105b7a99be72e3fe5', False)
    assert not response.cache_control
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 60
    response.headers['Content-Length'] = len(response.data)
    assert response.headers['Cache-Control'] == 'must-revalidate, max-age=60'

    env = create_environ()
    env.update({
        'REQUEST_METHOD':       'GET',
        'HTTP_IF_NONE_MATCH':   response.get_etag()[0]
    })
    response.make_conditional(env)

    # after the thing is invoked by the server as wsgi application
    # (we're emulating this here), there must not be any entity
    # headers left and the status code would have to be 304
    resp = Response.from_app(response, env)
    assert resp.status_code == 304
    assert not 'content-length' in resp.headers


def test_etag_response_mixin_freezing():
    """Freeze of the etag response mixin adds etag if mixed first"""
    class WithFreeze(ETagResponseMixin, BaseResponse):
        pass
    class WithoutFreeze(BaseResponse, ETagResponseMixin):
        pass

    response = WithFreeze('Hello World')
    response.freeze()
    assert response.get_etag() == (generate_etag('Hello World'), False)
    response = WithoutFreeze('Hello World')
    response.freeze()
    assert response.get_etag() == (None, None)
    response = Response('Hello World')
    response.freeze()
    assert response.get_etag() == (None, None)


def test_authenticate_mixin():
    """Test the authenciate mixin of the response"""
    resp = Response()
    resp.www_authenticate.type = 'basic'
    resp.www_authenticate.realm = 'Testing'
    assert resp.headers['WWW-Authenticate'] == 'Basic realm="Testing"'
    resp.www_authenticate.realm = None
    resp.www_authenticate.type = None
    assert 'WWW-Authenticate' not in resp.headers


def test_response_stream_mixin():
    """Response stream response-wrapper mixin"""
    response = Response()
    response.stream.write('Hello ')
    response.stream.write('World!')
    assert response.response == ['Hello ', 'World!']
    assert response.data == 'Hello World!'


def test_common_response_descriptors_mixin():
    """Common response descriptors response-wrapper mixin"""
    response = Response()
    response.mimetype = 'text/html'
    assert response.mimetype == 'text/html'
    assert response.content_type == 'text/html; charset=utf-8'
    assert response.mimetype_params == {'charset': 'utf-8'}
    response.mimetype_params['x-foo'] = 'yep'
    del response.mimetype_params['charset']
    assert response.content_type == 'text/html; x-foo=yep'

    now = datetime.utcnow().replace(microsecond=0)

    assert response.content_length is None
    response.content_length = '42'
    assert response.content_length == 42

    for attr in 'date', 'age', 'expires':
        assert getattr(response, attr) is None
        setattr(response, attr, now)
        assert getattr(response, attr) == now

    assert response.retry_after is None
    response.retry_after = now
    assert response.retry_after == now

    assert not response.vary
    response.vary.add('Cookie')
    response.vary.add('Content-Language')
    assert 'cookie' in response.vary
    assert response.vary.to_header() == 'Cookie, Content-Language'
    response.headers['Vary'] = 'Content-Encoding'
    assert response.vary.as_set() == set(['content-encoding'])

    response.allow.update(['GET', 'POST'])
    assert response.headers['Allow'] == 'GET, POST'

    response.content_language.add('en-US')
    response.content_language.add('fr')
    assert response.headers['Content-Language'] == 'en-US, fr'


def test_common_request_descriptors_mixin():
    """Common request descriptors request-wrapper mixin"""
    request = Request.from_values(content_type='text/html; charset=utf-8',
                                  content_length='23',
                                  headers={
        'Referer':      'http://www.example.com/',
        'Date':         'Sat, 28 Feb 2009 19:04:35 GMT',
        'Max-Forwards': '10',
        'Pragma':       'no-cache'
    })

    assert request.content_type == 'text/html; charset=utf-8'
    assert request.mimetype == 'text/html'
    assert request.mimetype_params == {'charset': 'utf-8'}
    assert request.content_length == 23
    assert request.referrer == 'http://www.example.com/'
    assert request.date == datetime(2009, 2, 28, 19, 4, 35)
    assert request.max_forwards == 10
    assert 'no-cache' in request.pragma


def test_shallow_mode():
    """Request object shallow mode"""
    request = Request({'QUERY_STRING': 'foo=bar'}, shallow=True)
    assert request.args['foo'] == 'bar'
    assert_raises(RuntimeError, lambda: request.form['foo'])


def test_form_parsing_failed():
    """Form parsing failed calls method on request object"""
    errors = []
    class TestRequest(Request):
        def _form_parsing_failed(self, error):
            errors.append(error)
    data = (
        '--blah\r\n'
    )
    data = TestRequest.from_values(input_stream=StringIO(data),
                                   content_length=len(data),
                                   content_type='multipart/form-data; boundary=foo',
                                   method='POST')
    assert not data.files
    assert not data.form
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)


def test_url_charset_reflection():
    """Make sure the URL charset is the same as the charset by default"""
    req = Request.from_values()
    req.charset = 'utf-7'
    assert req.url_charset == 'utf-7'


def test_response_streamed():
    """Test the `is_streamed` property of a response"""
    r = Response()
    assert not r.is_streamed
    r = Response("Hello World")
    assert not r.is_streamed
    r = Response(["foo", "bar"])
    assert not r.is_streamed
    def gen():
        if 0:
            yield None
    r = Response(gen())
    assert r.is_streamed


def test_response_freeze():
    """Response freezing"""
    def generate():
        yield "foo"
        yield "bar"
    resp = Response(generate())
    resp.freeze()
    assert resp.response == ['foo', 'bar']
    assert resp.headers['content-length'] == '6'


def test_other_method_payload():
    """Stream limiting for unknown methods"""
    data = 'Hello World'
    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='text/plain',
                              method='WHAT_THE_FUCK')
    assert req.data == data
    assert isinstance(req.stream, LimitedStream)


def test_urlfication():
    """Make sure Responses use URLs in headers"""
    resp = Response()
    resp.headers['Location'] = u'http://üser:pässword@☃.net/påth'
    resp.headers['Content-Location'] = u'http://☃.net/'
    headers = resp.get_wsgi_headers(create_environ())
    assert headers['location'] == \
        'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'
    assert headers['content-location'] == 'http://xn--n3h.net/'


def test_new_response_iterator_behavior():
    """New response iterator encoding behavior"""
    req = Request.from_values()
    resp = Response(u'Hello Wörld!')

    def get_content_length(resp):
        headers = Headers.linked(resp.get_wsgi_headers(req.environ))
        return headers.get('content-length', type=int)

    def generate_items():
        yield "Hello "
        yield u"Wörld!"

    # werkzeug encodes when set to `data` now, which happens
    # if a string is passed to the response object.
    assert resp.response == [u'Hello Wörld!'.encode('utf-8')]
    assert resp.data == u'Hello Wörld!'.encode('utf-8')
    assert get_content_length(resp) == 13
    assert not resp.is_streamed
    assert resp.is_sequence

    # try the same for manual assignment
    resp.data = u'Wörd'
    assert resp.response == [u'Wörd'.encode('utf-8')]
    assert resp.data == u'Wörd'.encode('utf-8')
    assert get_content_length(resp) == 5
    assert not resp.is_streamed
    assert resp.is_sequence

    # automatic generator sequence conversion
    resp.response = generate_items()
    assert resp.is_streamed
    assert not resp.is_sequence
    assert resp.data == u'Hello Wörld!'.encode('utf-8')
    assert resp.response == ['Hello ', u'Wörld!'.encode('utf-8')]
    assert not resp.is_streamed
    assert resp.is_sequence

    # automatic generator sequence conversion
    resp.response = generate_items()
    resp.implicit_seqence_conversion = False
    assert resp.is_streamed
    assert not resp.is_sequence
    assert_raises(RuntimeError, lambda: resp.data)
    resp.make_sequence()
    assert resp.data == u'Hello Wörld!'.encode('utf-8')
    assert resp.response == ['Hello ', u'Wörld!'.encode('utf-8')]
    assert not resp.is_streamed
    assert resp.is_sequence

    # stream makes it a list no matter how the conversion is set
    for val in True, False:
        resp.implicit_seqence_conversion = val
        resp.response = ("foo", "bar")
        assert resp.is_sequence
        resp.stream.write('baz')
        assert resp.response == ['foo', 'bar', 'baz']


def test_form_data_ordering():
    """Make sure that the wrapper support custom structures."""
    class MyRequest(Request):
        parameter_storage_class = ImmutableOrderedMultiDict

    req = MyRequest.from_values('/?foo=1&bar=0&foo=3')
    assert list(req.args) == ['foo', 'bar']
    assert req.args.items(multi=True) == [
        ('foo', '1'),
        ('bar', '0'),
        ('foo', '3')
    ]
    assert isinstance(req.args, ImmutableOrderedMultiDict)
    assert isinstance(req.values, CombinedMultiDict)
    assert req.values['foo'] == '1'
    assert req.values.getlist('foo') == ['1', '3']


def test_storage_classes():
    """Test custom storage classes to be used for incoming data."""
    class MyRequest(Request):
        dict_storage_class = dict
        list_storage_class = list
        parameter_storage_class = dict
    req = MyRequest.from_values('/?foo=baz', headers={
        'Cookie':   'foo=bar'
    })
    assert type(req.cookies) is dict
    assert req.cookies == {'foo': 'bar'}
    assert type(req.access_route) is list

    assert type(req.args) is dict
    assert type(req.values) is CombinedMultiDict
    assert req.values['foo'] == 'baz'

    req = Request.from_values(headers={
        'Cookie':   'foo=bar'
    })
    assert type(req.cookies) is ImmutableTypeConversionDict
    assert req.cookies == {'foo': 'bar'}
    assert type(req.access_route) is ImmutableList

    MyRequest.list_storage_class = tuple
    req = MyRequest.from_values()
    assert type(req.access_route) is tuple


def test_response_headers_passthrough():
    """If headers are a Headers object they will be stored on the response"""
    headers = Headers()
    resp = Response(headers=headers)
    assert resp.headers is headers
