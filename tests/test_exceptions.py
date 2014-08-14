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

from tests import WerkzeugTests

from werkzeug import exceptions
from werkzeug.wrappers import Response
from werkzeug._compat import text_type


class TestExceptions(WerkzeugTests):

    def test_proxy_exception(self):
        orig_resp = Response('Hello World')
        try:
            exceptions.abort(orig_resp)
        except exceptions.HTTPException as e:
            resp = e.get_response({})
        else:
            self.fail('exception not raised')
        self.assert_true(resp is orig_resp)
        self.assert_equal(resp.get_data(), b'Hello World')

    def test_aborter(self):
        abort = exceptions.abort
        pytest.raises(exceptions.BadRequest, abort, 400)
        pytest.raises(exceptions.Unauthorized, abort, 401)
        pytest.raises(exceptions.Forbidden, abort, 403)
        pytest.raises(exceptions.NotFound, abort, 404)
        pytest.raises(exceptions.MethodNotAllowed, abort, 405, ['GET', 'HEAD'])
        pytest.raises(exceptions.NotAcceptable, abort, 406)
        pytest.raises(exceptions.RequestTimeout, abort, 408)
        pytest.raises(exceptions.Gone, abort, 410)
        pytest.raises(exceptions.LengthRequired, abort, 411)
        pytest.raises(exceptions.PreconditionFailed, abort, 412)
        pytest.raises(exceptions.RequestEntityTooLarge, abort, 413)
        pytest.raises(exceptions.RequestURITooLarge, abort, 414)
        pytest.raises(exceptions.UnsupportedMediaType, abort, 415)
        pytest.raises(exceptions.UnprocessableEntity, abort, 422)
        pytest.raises(exceptions.InternalServerError, abort, 500)
        pytest.raises(exceptions.NotImplemented, abort, 501)
        pytest.raises(exceptions.BadGateway, abort, 502)
        pytest.raises(exceptions.ServiceUnavailable, abort, 503)
        pytest.raises(exceptions.GatewayTimeout, abort, 504)
        pytest.raises(exceptions.HTTPVersionNotSupported, abort, 505)

        myabort = exceptions.Aborter({1: exceptions.NotFound})
        pytest.raises(LookupError, myabort, 404)
        pytest.raises(exceptions.NotFound, myabort, 1)

        myabort = exceptions.Aborter(extra={1: exceptions.NotFound})
        pytest.raises(exceptions.NotFound, myabort, 404)
        pytest.raises(exceptions.NotFound, myabort, 1)

    def test_exception_repr(self):
        exc = exceptions.NotFound()
        self.assert_equal(text_type(exc), '404: Not Found')
        self.assert_equal(repr(exc), "<NotFound '404: Not Found'>")

        exc = exceptions.NotFound('Not There')
        self.assert_equal(text_type(exc), '404: Not Found')
        self.assert_equal(repr(exc), "<NotFound '404: Not Found'>")

    def test_special_exceptions(self):
        exc = exceptions.MethodNotAllowed(['GET', 'HEAD', 'POST'])
        h = dict(exc.get_headers({}))
        self.assert_equal(h['Allow'], 'GET, HEAD, POST')
        self.assert_true('The method is not allowed' in exc.get_description())
