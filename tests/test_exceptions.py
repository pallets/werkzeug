# -*- coding: utf-8 -*-
"""
    tests.exceptions
    ~~~~~~~~~~~~~~~~

    The tests for the exception classes.

    TODO:

    -   This is undertested.  HTML is never checked

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest

from werkzeug import exceptions
from werkzeug.wrappers import Response
from werkzeug._compat import text_type


def test_proxy_exception():
    orig_resp = Response('Hello World')
    with pytest.raises(exceptions.HTTPException) as excinfo:
        exceptions.abort(orig_resp)
    resp = excinfo.value.get_response({})
    assert resp is orig_resp
    assert resp.get_data() == b'Hello World'


@pytest.mark.parametrize('test', [
    (exceptions.BadRequest, 400),
    (exceptions.Unauthorized, 401),
    (exceptions.Forbidden, 403),
    (exceptions.NotFound, 404),
    (exceptions.MethodNotAllowed, 405, ['GET', 'HEAD']),
    (exceptions.NotAcceptable, 406),
    (exceptions.RequestTimeout, 408),
    (exceptions.Gone, 410),
    (exceptions.LengthRequired, 411),
    (exceptions.PreconditionFailed, 412),
    (exceptions.RequestEntityTooLarge, 413),
    (exceptions.RequestURITooLarge, 414),
    (exceptions.UnsupportedMediaType, 415),
    (exceptions.UnprocessableEntity, 422),
    (exceptions.InternalServerError, 500),
    (exceptions.NotImplemented, 501),
    (exceptions.BadGateway, 502),
    (exceptions.ServiceUnavailable, 503)
])
def test_aborter_general(test):
    exc_type = test[0]
    args = test[1:]

    with pytest.raises(exc_type) as exc_info:
        exceptions.abort(*args)
    assert type(exc_info.value) is exc_type


def test_aborter_custom():
    myabort = exceptions.Aborter({1: exceptions.NotFound})
    pytest.raises(LookupError, myabort, 404)
    pytest.raises(exceptions.NotFound, myabort, 1)

    myabort = exceptions.Aborter(extra={1: exceptions.NotFound})
    pytest.raises(exceptions.NotFound, myabort, 404)
    pytest.raises(exceptions.NotFound, myabort, 1)


def test_exception_repr():
    exc = exceptions.NotFound()
    assert text_type(exc) == '404: Not Found'
    assert repr(exc) == "<NotFound '404: Not Found'>"

    exc = exceptions.NotFound('Not There')
    assert text_type(exc) == '404: Not Found'
    assert repr(exc) == "<NotFound '404: Not Found'>"


def test_special_exceptions():
    exc = exceptions.MethodNotAllowed(['GET', 'HEAD', 'POST'])
    h = dict(exc.get_headers({}))
    assert h['Allow'] == 'GET, HEAD, POST'
    assert 'The method is not allowed' in exc.get_description()
