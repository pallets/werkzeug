==========================
Request / Response Objects
==========================

.. module:: werkzeug.wrappers

The request and response objects wrap the WSGI environment or the return
value from a WSGI application so that it is another WSGI application
(wraps a whole application).

How they Work
=============

Your WSGI application is always passed two arguments.  The WSGI "environment"
and the WSGI `start_response` function that is used to start the response
phase.  The :class:`Request` class wraps the `environ` for easier access to
request variables (form data, request headers etc.).

The :class:`Response` on the other hand is a standard WSGI application that
you can create.  The simple hello world in Werkzeug looks like this::

    from werkzeug.wrappers import Response
    application = Response('Hello World!')

To make it more useful you can replace it with a function and do some
processing::

    from werkzeug.wrappers import Request, Response

    def application(environ, start_response):
        request = Request(environ)
        response = Response(f"Hello {request.args.get('name', 'World!')}!")
        return response(environ, start_response)

Because this is a very common task the :class:`~Request` object provides
a helper for that.  The above code can be rewritten like this::

    from werkzeug.wrappers import Request, Response

    @Request.application
    def application(request):
        return Response(f"Hello {request.args.get('name', 'World!')}!")

The `application` is still a valid WSGI application that accepts the
environment and `start_response` callable.


Mutability and Reusability of Wrappers
======================================

The implementation of the Werkzeug request and response objects are trying
to guard you from common pitfalls by disallowing certain things as much as
possible.  This serves two purposes: high performance and avoiding of
pitfalls.

For the request object the following rules apply:

1. The request object is immutable.  Modifications are not supported by
   default, you may however replace the immutable attributes with mutable
   attributes if you need to modify it.
2. The request object may be shared in the same thread, but is not thread
   safe itself.  If you need to access it from multiple threads, use
   locks around calls.
3. It's not possible to pickle the request object.

For the response object the following rules apply:

1. The response object is mutable
2. The response object can be pickled or copied after `freeze()` was
   called.
3. Since Werkzeug 0.6 it's safe to use the same response object for
   multiple WSGI responses.
4. It's possible to create copies using `copy.deepcopy`.


Wrapper Classes
===============

.. autoclass:: Request
    :members:
    :inherited-members:

    .. automethod:: _get_file_stream


.. autoclass:: Response
    :members:
    :inherited-members:

    .. automethod:: __call__

    .. automethod:: _ensure_sequence
