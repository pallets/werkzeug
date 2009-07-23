===============
Data Structures
===============

.. module:: werkzeug

Werkzeug provides some subclasses of common Python objects to extend them
with additional features.  Some of them are used to make them immutable, others
are used to change some semantics to better work with HTTP.

You can import all these objects directly from :mod:`werkzeug`.

General Purpose
===============

.. autoclass:: TypeConversionDict
   :members:

.. autoclass:: ImmutableTypeConversionDict
   :members: copy

.. autoclass:: MultiDict
   :members:
   :inherited-members:

.. autoclass:: ImmutableMultiDict
   :members: copy

.. autoclass:: CombinedMultiDict

.. autoclass:: ImmutableDict
   :members: copy

.. autoclass:: ImmutableList

.. autoclass:: FileMultiDict
   :members:

HTTP Related
============

.. autoclass:: Headers([defaults])
   :members:

.. autoclass:: EnvironHeaders

.. autoclass:: HeaderSet
   :members:

.. autoclass:: Accept
   :members:

.. autoclass:: MIMEAccept
   :members: accept_html, accept_xhtml

.. autoclass:: CharsetAccept

.. autoclass:: LanguageAccept

.. autoclass:: RequestCacheControl
   :members:

   .. autoattribute:: no_cache

   .. autoattribute:: no_store

   .. autoattribute:: max_age

   .. autoattribute:: no_transform

.. autoclass:: ResponseCacheControl
   :members:

   .. autoattribute:: no_cache

   .. autoattribute:: no_store

   .. autoattribute:: max_age

   .. autoattribute:: no_transform

.. autoclass:: ETags
   :members:

.. autoclass:: Authorization
   :members:

.. autoclass:: WWWAuthenticate
   :members:


Others
======

.. autoclass:: FileStorage
   :members:

   .. attribute:: stream

      The input stream for the uploaded file.  This usually points to an
      open temporary file.

   .. attribute:: filename

      The filename of the file on the client.

   .. attribute:: name

      The name of the form field.

   .. attribute:: content_type

      The content type (mimetype) of the file.

   .. attribute:: content_length

      The length of the file in bytes.

   .. attribute:: headers

      The multipart headers as :class:`Headers` object.  This usually contains
      irrelevant information but in combination with custom multipart requests
      the raw headers might be interesting.

      .. versionadded:: 0.6
