========
Wrappers
========

.. module:: werkzeug

You can import all these objects directly from :mod:`werkzeug`.

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

.. autoclass:: CommonResponseDescriptorsMixin
   :members:

.. autoclass:: WWWAuthenticateMixin
   :members:

.. autoclass:: UserAgentMixin
   :members:
