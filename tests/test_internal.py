# -*- coding: utf-8 -*-
from nose.tools import assert_raises

from warnings import filterwarnings, resetwarnings
from datetime import datetime
from werkzeug import _internal as internal, Request, Response, \
     create_environ


def test_date_to_unix():
    """Date to UNIX timestamp conversions."""
    assert internal._date_to_unix(datetime(1970, 1, 1)) == 0
    assert internal._date_to_unix(datetime(1970, 1, 1, 1, 0, 0)) == 3600
    assert internal._date_to_unix(datetime(1970, 1, 1, 1, 1, 1)) == 3661
    x = datetime(2010, 2, 15, 16, 15, 39)
    assert internal._date_to_unix(x) == 1266250539


def test_easteregg():
    """Make sure the easteregg runs"""
    req = Request.from_values('/?macgybarchakku')
    resp = Response.force_type(internal._easteregg(None), req)
    assert 'About Werkzeug' in resp.data
    assert 'the Swiss Army knife of Python web development' in resp.data


def test_wrapper_internals():
    """Test internals of the wrappers"""
    from werkzeug import Request
    req = Request.from_values(data={'foo': 'bar'}, method='POST')
    req._load_form_data()
    assert req.form.to_dict() == {'foo': 'bar'}

    # second call does not break
    req._load_form_data()
    assert req.form.to_dict() == {'foo': 'bar'}

    # check reprs
    assert repr(req) == "<Request 'http://localhost/' [POST]>"
    resp = Response()
    assert repr(resp) == '<Response 0 bytes [200 OK]>'
    resp.data = 'Hello World!'
    assert repr(resp) == '<Response 12 bytes [200 OK]>'
    resp.response = iter(['Test'])
    assert repr(resp) == '<Response streamed [200 OK]>'

    # unicode data does not set content length
    response = Response([u'Hällo Wörld'])
    headers = response.get_wsgi_headers(create_environ())
    assert 'Content-Length' not in headers

    response = Response(['Hällo Wörld'])
    headers = response.get_wsgi_headers(create_environ())
    assert 'Content-Length' in headers

    # check for internal warnings
    print 'start'
    filterwarnings('error', category=Warning)
    response = Response()
    environ = create_environ()
    response.response = 'What the...?'
    assert_raises(Warning, lambda: list(response.iter_encoded()))
    assert_raises(Warning, lambda: list(response.get_app_iter(environ)))
    response.direct_passthrough = True
    assert_raises(Warning, lambda: list(response.iter_encoded()))
    assert_raises(Warning, lambda: list(response.get_app_iter(environ)))
    resetwarnings()
