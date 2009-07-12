========
Wrappers
========

.. module:: werkzeug

You can import all these objects directly from :mod:`werkzeug`.  Wrappers wrap
the WSGI environment or the return value from a WSGI application so that it
is another WSGI application (wraps a whole application).

How they Work
=============

Your WSGI application is always passed two arguments.  The WSGI "environment"
and the WSGI `start_response` function that is used to start the response
phase.  The :class:`Request` class wraps the `environ` for easier access to
request variables (form data, request headers etc.).

The :class:`Response` on the other hand is a standard WSGI application that
you can create.  The simple hello world in Werkzeug looks like this::

    from werkzeug import Response
    application = Response('Hello World!')

To make it more useful you can replace it with a function and do some
processing::

    from werkzeug import Request, Response

    def application(environ, start_response):
        request = Request(environ)
        response = Response("Hello %s!" % request.args.get('name', 'World!'))
        return response(environ, start_response)

Because this is a very common task the :class:`~Request` object provides
a helper for that.  The above code can be rewritten like this::

    from werkzeug import Request, Response

    @Request.application
    def application(request):
        return Response("Hello %s!" % request.args.get('name', 'World!'))

The `application` is still a valid WSGI application that accepts the
environment and `start_response` callable.


Base Wrappers
=============

These objects implement a common set of operations.  They are missing fancy
addon functionality like user agent parsing or etag handling.  These features
are available by mixing in various mixin classes or using :class:`Request` and
:class:`Response`.

.. autoclass:: BaseRequest
   :members:

   .. attribute:: environ

      The WSGI environment that the request object uses for data retrival.

   .. attribute:: shallow

      `True` if this request object is shallow (does not modify :attr:`environ`),
      `False` otherwise.

   .. automethod:: _get_file_stream

   .. automethod:: _form_parsing_failed


.. autoclass:: BaseResponse
   :members:

   .. attribute:: response

      The application iterator.  If constructed from a string this will be a
      list, otherwise the object provided as application iterator.  (The first
      argument passed to :class:`BaseResponse`)

   .. attribute:: headers

      A :class:`Headers` object representing the response headers.

   .. attribute:: status_code

      The response status as integer.

   .. attribute:: direct_passthrough

      If ``direct_passthrough=True`` was passed to the response object or if
      this attribute was set to `True` before using the response object as
      WSGI application, the wrapped iterator is returned unchanged.  This
      makes it possible to pass a special `wsgi.file_wrapper` to the response
      object.  See :func:`wrap_file` for more details.

   .. automethod:: __call__


Mixin Classes
=============

Werkzeug also provides helper mixins for various HTTP related functionality
such as etags, cache control, user agents etc.  When subclassing you can
mix those classes in to extend the functionality of the :class:`BaseRequest`
or :class:`BaseResponse` object.  Here a small example for a request object
that parses accept headers::

    from werkzeug import BaseRequest, AcceptMixin

    class Request(BaseRequest, AcceptMixin):
        pass

The :class:`Request` and :class:`Response` classes subclass the :class:`BaseRequest`
and :class:`BaseResponse` classes and implement all the mixins Werkzeug provides:


.. autoclass:: Request

.. autoclass:: Response

.. autoclass:: AcceptMixin
   :members:

.. autoclass:: AuthorizationMixin
   :members:

.. autoclass:: ETagRequestMixin
   :members:

.. autoclass:: ETagResponseMixin
   :members:

.. autoclass:: ResponseStreamMixin
   :members:

.. autoclass:: CommonRequestDescriptorsMixin
   :members:

.. autoclass:: CommonResponseDescriptorsMixin
   :members:

.. autoclass:: WWWAuthenticateMixin
   :members:

.. autoclass:: UserAgentMixin
   :members:
