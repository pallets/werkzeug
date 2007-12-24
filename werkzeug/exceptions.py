# -*- coding: utf-8 -*-
"""
    werkzeug.exceptions
    ~~~~~~~~~~~~~~~~~~~

    This module implements exceptions for the most important HTTP status
    codes.  Each exception is a small WSGI application you can return
    in views.  Simple usage example would look like this::

        from werkzeug.exceptions import HTTPException, NotFound

        def application(environ, start_response):
            request = Request(environ)
            try:
                response = view_func(request)
            except NotFound:
                response = get_not_found_response(request)
            except HTTPException, e:
                response = e
            return response(environ, start_response)

    This module does only implement error classes for status codes from
    400 onwards.  Everything below that is not a real error and should be
    returned as normal response in the python layer too because of that.

    Unused exception such as 402 don't have their predefined subclasses
    but you can easily fill the gap by doing that yourself.

    If you're looking for redirection helpers have a look into the utils
    module which implements a `redirect` function that generates a simple
    redirect response.


    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.utils import escape
from werkzeug.wrappers import BaseResponse
from werkzeug.http import HTTP_STATUS_CODES


class HTTPException(Exception):
    """
    Baseclass for all HTTP exceptions.
    """

    code = None
    description = None

    def __init__(self):
        Exception.__init__(self)

    def name(self):
        """The status name."""
        return HTTP_STATUS_CODES[self.code]
    name = property(name, doc=name.__doc__)

    def get_description(self, environ):
        """Get the description."""
        return self.description

    def get_body(self, environ):
        """Get the HTML body."""
        return (
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
            '<title>%(code)s %(name)s</title>\n'
            '<h1>%(name)s</h1>\n'
            '%(description)s\n'
        ) % {
            'code':         self.code,
            'name':         escape(self.name),
            'description':  self.get_description(environ)
        }

    def get_headers(self, environ):
        """Get a list of headers."""
        return [('Content-Type', 'text/html')]

    def get_response(self, environ):
        """Get a response object."""
        headers = self.get_headers(environ)
        return BaseResponse(self.get_body(environ), self.code, headers)

    def __call__(self, environ, start_response):
        response = self.get_response(environ)
        return response(environ, start_response)


class BadRequest(HTTPException):
    code = 400
    description = (
        '<p>The browser (or proxy) sent a request that this server could '
        'not understand.</p>'
    )


class Unauthorized(HTTPException):
    code = 401
    description = (
        '<p>The server could not verify that you are authorized to access '
        'the URL requested.  You either supplied the wrong credentials (e.g.'
        ', bad password), or your browser doesn\'t understand how to supply '
        'the credentials required.</p><p>In case you are allowed to request '
        'the document, please check your user-id and password and try '
        'again.</p>'
    )


class Forbidden(HTTPException):
    code = 403
    description = (
        '<p>You don\'t have the permission to access the requested resource. '
        'It is either read-protected or not readable by the server.</p>'
    )


class NotFound(HTTPException):
    code = 404
    description = (
        '<p>The requested URL was not found on the server.</p>'
        '<p>If you entered the URL manually please check your spelling and '
        'try again.</p>'
    )


class MethodNotAllowed(HTTPException):
    code = 405

    def __init__(self, valid_methods=None):
        """
        takes an optional list of valid http methods
        starting with werkzeug 0.3 the list will be mandatory
        """
        HTTPException.__init__(self)
        self.valid_methods = valid_methods

    def get_headers(self, environ):
        headers = HTTPException.get_headers(self, environ)
        if self.valid_methods:
            headers.append(('Allow', ', '.join(self.valid_methods)))
        return headers

    def get_description(self, environ):
        m = escape(environ.get('REQUEST_METHOD', 'GET'))
        return '<p>The method %s is not allowed for the requested URL.</p>' % m


class NotAcceptable(HTTPException):
    code = 406

    description = (
        '<p>The resource identified by the request is only capable of generating response entities '
        'which have content characteristics not acceptable '
        'according to the accept headers sent in the request.</p>'
        )


class RequestTimeout(HTTPException):
    code = 408
    description = (
        '<p>The server closed the network connection because the browser '
        'didn\'t finish the request within the specified time.</p>'
    )


class Gone(HTTPException):
    code = 410
    description = (
        '<p>The requested URL is no longer available on this server and '
        'there is no forwarding address.</p><p>If you followed a link '
        'from a foreign page, please contact the author of this page.'
    )


class LengthRequired(HTTPException):
    code = 411
    description = (
        '<p>A request with this method requires a valid <code>Content-'
        'Lenght</code> header.</p>'
    )


class PreconditionFailed(HTTPException):
    code = 412
    description = (
        '<p>The precondition on the request for the URL failed positive '
        'evaluation.</p>'
    )


class RequestEntityTooLarge(HTTPException):
    code = 413
    description = (
        '<p>The data value transmitted exceed the capacity limit.</p>'
    )


class RequestURITooLarge(HTTPException):
    code = 414
    description = (
        '<p>The length of the requested URL exceeds the capacity limit '
        'for this server.  The request cannot be processed.</p>'
    )


class UnsupportedMediaType(HTTPException):
    code = 415
    description = (
        '<p>The server does not support the media type transmitted in '
        'the request.</p>'
    )


class InternalServerError(HTTPException):
    code = 500
    description = (
        '<p>The server encountered an internal error and was unable to '
        'complete your request.  Either the server is overloaded or there '
        'is an error in the application.</p>'
    )


class NotImplemented(HTTPException):
    code = 501
    description = (
        '<p>The server does not support the action requested by the '
        'browser.</p>'
    )


class BadGateway(HTTPException):
    code = 502
    description = (
        '<p>The proxy server received an invalid response from an upstream '
        'server.</p>'
    )


class ServiceUnavailable(HTTPException):
    code = 503
    description = (
        '<p>The server is temporarily unable to service your request due to '
        'maintenance downtime or capacity problems.  Please try again '
        'later.</p>'
    )
