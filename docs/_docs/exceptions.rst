===============
HTTP Exceptions
===============

.. module:: werkzeug.exceptions

.. docstring:: . [3:-3]


Error Classes
=============

The following error classes exist in Werkzeug:

.. autoclass:: BadRequest

.. autoclass:: Unauthorized

.. autoclass:: Forbidden

.. autoclass:: NotFound

.. autoclass:: MethodNotAllowed

.. autoclass:: NotAcceptable

.. autoclass:: RequestTimeout

.. autoclass:: Gone

.. autoclass:: LengthRequired

.. autoclass:: PreconditionFailed

.. autoclass:: RequestEntityTooLarge

.. autoclass:: RequestURITooLarge

.. autoclass:: UnsupportedMediaType

.. autoclass:: InternalServerError

.. autoclass:: NotImplemented

.. autoclass:: BadGateway

.. autoclass:: ServiceUnavailable


Baseclass
=========

All the exceptions implement this common interface:

.. autoclass:: HTTPException
   :members: get_response, __call__


Special HTTP Exceptions
=======================

Starting with Werkzeug 0.3 some of the builtin classes raise exceptions that
look like regular python exceptions (eg `KeyError`) but are :exc:`BadRequest`
HTTP exceptions at the same time.  This decision was made to simplify a
common pattern where you want to abort if the client tampered with the
submitted form data in a way that the application can't recover properly and
should abort with ``400 BAD REQUEST``.

Assuming the application catches all HTTP exceptions and reacts to them
properly a view function could do the following savely and doesn't have to
check if the keys exist::

    def new_post(request):
        post = Post(title=request.form['title'], body=request.form['body'])
        post.save()
        return redirect(post.url)

If `title` or `body` are missing in the form a special key error will be
raised which behaves like a `KeyError` but also a :exc:`BadRequest` exception.


Simple Aborting
===============

Sometimes it's convenient to just raise an exception by the error code,
without importing the exception and looking up the name etc.  For this
purpose there is the :func:`abort` function.

It can be passed a WSGI application or a status code.  If a status code
is given it's looked up in the list of exceptions from above and will
raise that exception, if passed a WSGI application it will wrap it in
a proxy WSGI exception and raise that::

    abort(404)
    abort(Response('Hello World'))

If you want to use this functionality with custom excetions you can
create an instance of the aborter class:

.. autoclass:: Aborter


Custom Errors
=============

As you can see from the list above not all status codes are available as
errors.  Especially redirects and ather non 200 status codes that
represent do not represent errors are missing.  For redirects you can use
the `redirect` function from the utilities.

If you want to add an error yourself you can subclass `HTTPException`::

    from werkzeug.exceptions import HTTPException

    class PaymentRequred(HTTPException):
        code = 402
        description = '<p>Payment required.</p>'

This is the minimal code you need for your own exception.  If you want to
add more logic to the errors you can override the `get_description()`,
`get_body()`, `get_headers()` and `get_response()` methods.  In any case
you should have a look at the sourcecode of the exceptions module.

You can override the default description in the constructor with the
`description` parameter (it's the first argument for all exceptions
except of the :exc:`MethodNotAllowed` which accepts a list of allowed methods
as first argument)::

    raise BadRequest('Request failed because X was not present')
