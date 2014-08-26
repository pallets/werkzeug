# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.exceptions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The tests for the exception classes.

    TODO:

    -   This is undertested.  HTML is never checked

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug import exceptions
from werkzeug.wrappers import Response
from werkzeug._compat import text_type


class ExceptionsTestCase(WerkzeugTestCase):

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

        for test in [
            (exceptions.BadRequest, abort, 400),
            (exceptions.Unauthorized, abort, 401),
            (exceptions.Forbidden, abort, 403),
            (exceptions.NotFound, abort, 404),
            (exceptions.MethodNotAllowed, abort, 405, ['GET', 'HEAD']),
            (exceptions.NotAcceptable, abort, 406),
            (exceptions.RequestTimeout, abort, 408),
            (exceptions.Gone, abort, 410),
            (exceptions.LengthRequired, abort, 411),
            (exceptions.PreconditionFailed, abort, 412),
            (exceptions.RequestEntityTooLarge, abort, 413),
            (exceptions.RequestURITooLarge, abort, 414),
            (exceptions.UnsupportedMediaType, abort, 415),
            (exceptions.UnprocessableEntity, abort, 422),
            (exceptions.InternalServerError, abort, 500),
            (exceptions.NotImplemented, abort, 501),
            (exceptions.BadGateway, abort, 502),
            (exceptions.ServiceUnavailable, abort, 503)
        ]:
            exc_type = test[0]
            func = test[1]
            args = test[2:]
            with self.assert_raises(exc_type) as exc_info:
                func(*args)

            self.assert_is(type(exc_info.exc_value), exc_type)

        myabort = exceptions.Aborter({1: exceptions.NotFound})
        self.assert_raises(LookupError, myabort, 404)
        self.assert_raises(exceptions.NotFound, myabort, 1)

        myabort = exceptions.Aborter(extra={1: exceptions.NotFound})
        self.assert_raises(exceptions.NotFound, myabort, 404)
        self.assert_raises(exceptions.NotFound, myabort, 1)

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


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExceptionsTestCase))
    return suite
