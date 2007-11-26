# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers test
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyright: 2007 by Armin Ronacher.
    :license: BSD license.
"""
import pickle
from werkzeug.wrappers import BaseResponse, BaseRequest
from werkzeug.utils import MultiDict
from werkzeug.test import Client


class RequestTestResponse(BaseResponse):
    """
    Subclass of the normal response class we use to test response
    and base classes.  Has some methods to test if things in the
    response match.
    """

    def __init__(self, response, status, headers):
        BaseResponse.__init__(self, response, status, headers)
        self.body_data = pickle.loads(self.response_body)

    def __getitem__(self, key):
        return self.body_data[key]


def request_test_app(environ, start_response):
    """Small test app."""
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


def assert_request_test_environ(environ, method):
    assert environ['REQUEST_METHOD'] == method
    assert environ['PATH_INFO'] == '/'
    assert environ['SCRIPT_NAME'] == ''
    assert environ['SERVER_NAME'] == 'localhost'
    assert environ['wsgi.version'] == (1, 0)
    assert environ['wsgi.url_scheme'] == 'http'


def test_request():
    client = Client(request_test_app, RequestTestResponse)

    # get requests
    response = client.get('/?foo=bar&foo=hehe')
    assert response['args'] == MultiDict([('foo', 'bar'), ('foo', 'hehe')])
    assert response['args_as_list'] == [('foo', ['bar', 'hehe'])]
    assert response['form'] == MultiDict()
    assert response['form_as_list'] == []
    assert response['data'] == ''
    assert_request_test_environ(response['environ'], 'GET')

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
    assert_request_test_environ(response['environ'], 'POST')

    # post requests with json data
    json = '{"foo": "bar", "blub": "blah"}'
    response = client.post('/?a=b', data=json, content_type='application/json')
    assert response['data'] == json
    assert response['args'] == MultiDict([('a', 'b')])
    assert response['form'] == MultiDict()


def test_response():
    # unicode
    response = BaseResponse(u'öäü')
    assert response.response_body == 'öäü'

    # writing
    response = BaseResponse('foo')
    response.write('bar')
    assert response.response_body == 'foobar'

    # set cookie
    response = BaseResponse()
    response.set_cookie('foo', 'bar', 60, 0, '/blub', 'example.org', False)
    print response.header_list
    assert response.header_list == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        # the leading whitespace is an implementation detail right now.  we
        # test for it though to keep the test simple.
        ('Set-Cookie', ' foo=bar; Domain=example.org; expires=Thu, '
         '01-Jan-1970 00:00:00 GMT; Max-Age=60; Path=/blub; secure')
    ]
