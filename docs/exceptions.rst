.. module:: werkzeug.exceptions

HTTP Exceptions
===============

These exceptions represent HTTP 4XX and 5XX error status codes. They can be
converted to an HTML response describing the error, and called as a WSGI
application to return that response.

When using the :meth:`.Request.application` decorator to write an
application, it automatically catches all ``HTTPException`` errors and
returns their response. Other frameworks built on Werkzeug do this as well.

.. code-block:: python

    from werkzeug import Request, Response
    from werkzeug.exceptions import NotFound

    @Request.application
    def app(request: Request) -> Response:
        if request.path != "/":
            raise NotFound()

        return Response("Hello, World!")


Base Class
----------

.. autoexception:: HTTPException
   :members: get_response, __call__


Error Classes
-------------

.. autoexception:: BadRequest

.. autoexception:: Unauthorized

.. autoexception:: Forbidden

.. autoexception:: NotFound

.. autoexception:: MethodNotAllowed

.. autoexception:: NotAcceptable

.. autoexception:: RequestTimeout

.. autoexception:: Conflict

.. autoexception:: Gone

.. autoexception:: LengthRequired

.. autoexception:: PreconditionFailed

.. autoexception:: RequestEntityTooLarge

.. autoexception:: RequestURITooLarge

.. autoexception:: UnsupportedMediaType

.. autoexception:: RequestedRangeNotSatisfiable

.. autoexception:: ExpectationFailed

.. autoexception:: ImATeapot

.. autoexception:: MisdirectedRequest

.. autoexception:: UnprocessableEntity

.. autoexception:: Locked

.. autoexception:: FailedDependency

.. autoexception:: PreconditionRequired

.. autoexception:: TooManyRequests

.. autoexception:: RequestHeaderFieldsTooLarge

.. autoexception:: UnavailableForLegalReasons

.. autoexception:: InternalServerError
    :members: original_exception

.. autoexception:: NotImplemented

.. autoexception:: BadGateway

.. autoexception:: ServiceUnavailable

.. autoexception:: GatewayTimeout

.. autoexception:: HTTPVersionNotSupported


Special Exceptions
------------------

.. autoexception:: BadRequestKeyError
    :show-inheritance:
    :members: show_exception

.. autoexception:: ClientDisconnected
    :show-inheritance:

.. autoexception:: SecurityError
    :show-inheritance:


Simple Aborting
---------------

The ``abort`` function can be used to raise an exception by status code,
rather than importing the specific exception.

.. autofunction:: abort

If you want to use this with custom exceptions, create an instance of the
``Aborter`` class.

.. autoclass:: Aborter
    :members: __call__


Other Status Codes
------------------

Werkzeug defines exceptions for many 4XX and 5XX error codes defined in modern
HTTP specs. If you need another error status as an exception, you can define
your own subclass.

Status codes that do not represent errors are not defined as exceptions. 2XX
responses can be created directly with the :class:`.Response` class. Use
:func:`.redirect` to create 3XX redirect responses.

To define a custom error, subclass :exc:`.HTTPException` and define the ``code``
class attribute. If Python's :class:`.HTTPStatus` defines that code, this is all
you need, it will pull the ``name`` and ``description`` from the enum.
Otherwise, define the ``name`` and ``description`` class attributes as well.

    from werkzeug.exceptions import HTTPException

    class PaymentRequired(HTTPException):
        code = 402

If you want to add custom behavior, such as a required header, you can override
``__init__`` to take arguments, and :meth:`.HTTPException.get_response` to
customize the response.
