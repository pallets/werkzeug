# -*- coding: utf-8 -*-
"""
    werkzeug.exceptiosn test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
from nose.tools import assert_raises

from werkzeug import exceptions, Response, abort, Aborter


def test_proxy_exception():
    """Proxy exceptions"""
    orig_resp = Response('Hello World')
    try:
        abort(orig_resp)
    except exceptions.HTTPException, e:
        resp = e.get_response({})
    else:
        assert False, 'exception not raised'
    assert resp is orig_resp
    assert resp.data == 'Hello World'


def test_aborter():
    """Exception aborter"""
    assert_raises(exceptions.BadRequest, abort, 400)
    assert_raises(exceptions.Unauthorized, abort, 401)
    assert_raises(exceptions.Forbidden, abort, 403)
    assert_raises(exceptions.NotFound, abort, 404)
    assert_raises(exceptions.MethodNotAllowed, abort, 405, ['GET', 'HEAD'])
    assert_raises(exceptions.NotAcceptable, abort, 406)
    assert_raises(exceptions.RequestTimeout, abort, 408)
    assert_raises(exceptions.Gone, abort, 410)
    assert_raises(exceptions.LengthRequired, abort, 411)
    assert_raises(exceptions.PreconditionFailed, abort, 412)
    assert_raises(exceptions.RequestEntityTooLarge, abort, 413)
    assert_raises(exceptions.RequestURITooLarge, abort, 414)
    assert_raises(exceptions.UnsupportedMediaType, abort, 415)
    assert_raises(exceptions.InternalServerError, abort, 500)
    assert_raises(exceptions.NotImplemented, abort, 501)
    assert_raises(exceptions.BadGateway, abort, 502)
    assert_raises(exceptions.ServiceUnavailable, abort, 503)

    myabort = Aborter({1: exceptions.NotFound})
    assert_raises(LookupError, myabort, 404)
    assert_raises(exceptions.NotFound, myabort, 1)

    myabort = Aborter(extra={1: exceptions.NotFound})
    assert_raises(exceptions.NotFound, myabort, 404)
    assert_raises(exceptions.NotFound, myabort, 1)


def test_exception_repr():
    """Repr and unicode of exceptions"""
    exc = exceptions.NotFound()
    assert unicode(exc) == '404: Not Found'
    assert repr(exc) == "<NotFound '404: Not Found'>"

    exc = exceptions.NotFound('Not There')
    assert unicode(exc) == '404: Not There'
    assert repr(exc) == "<NotFound '404: Not There'>"


def test_special_exceptions():
    """Special HTTP exceptions"""
    exc = exceptions.MethodNotAllowed(['GET', 'HEAD', 'POST'])
    h = dict(exc.get_headers({}))
    assert h['Allow'] == 'GET, HEAD, POST'
    assert 'The method DELETE is not allowed' in exc.get_description({
        'REQUEST_METHOD': 'DELETE'
    })
