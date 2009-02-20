# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers test
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import pickle

from nose.tools import assert_raises

from datetime import datetime, timedelta
from werkzeug.wrappers import *
from werkzeug.utils import MultiDict
from werkzeug.test import Client


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
    assert response.header_list == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Set-Cookie', 'foo=bar; Domain=example.org; expires=Thu, '
         '01-Jan-1970 00:00:00 GMT; Max-Age=60; Path=/blub')
    ]


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
    assert_raises(TypeError, "SpecialResponse.force_type(wsgi_application)")


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


def test_etag_request_mixin():
    """ETag request-wrapper mixin"""
    request = Request({
        'HTTP_CACHE_CONTROL':       'private, no-cache',
        'HTTP_IF_MATCH':            'w/"foo", bar, "baz"',
        'HTTP_IF_NONE_MATCH':       'w/"foo", bar, "baz"',
        'HTTP_IF_MODIFIED_SINCE':   'Tue, 22 Jan 2008 11:18:44 GMT',
        'HTTP_IF_UNMODIFIED_SINCE': 'Tue, 22 Jan 2008 11:18:44 GMT'
    })
    assert request.cache_control.private
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


def test_etag_response_mixin():
    """ETag response-wrapper mixin"""
    response = Response('Hello World')
    assert response.get_etag() == (None, None)
    response.add_etag()
    assert response.get_etag() == ('b10a8db164e0754105b7a99be72e3fe5', False)
    assert not response.cache_control
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 60
    assert response.headers['Cache-Control'] == 'must-revalidate, max-age=60'

    response.make_conditional({
        'REQUEST_METHOD':       'GET',
        'HTTP_IF_NONE_MATCH':   response.get_etag()[0]
    })
    assert response.status_code == 304


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


def test_shallow_mode():
    """Request object shallow mode"""
    request = Request({'QUERY_STRING': 'foo=bar'}, shallow=True)
    assert request.args['foo'] == 'bar'
    assert_raises(RuntimeError, lambda: request.form['foo'])
