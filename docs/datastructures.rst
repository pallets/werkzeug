===============
Data Structures
===============

.. module:: werkzeug.datastructures

Werkzeug provides some subclasses of common Python objects to extend them
with additional features.  Some of them are used to make them immutable, others
are used to change some semantics to better work with HTTP.

General Purpose
===============

.. versionchanged:: 0.6
   The general purpose classes are now pickleable in each protocol as long
   as the contained objects are pickleable.  This means that the
   :class:`FileMultiDict` won't be pickleable as soon as it contains a
   file.

.. autoclass:: TypeConversionDict
   :members:

.. autoclass:: ImmutableTypeConversionDict
   :members: copy

.. autoclass:: MultiDict
   :members:
   :inherited-members:

.. autoclass:: OrderedMultiDict

.. autoclass:: ImmutableMultiDict
   :members: copy

.. autoclass:: ImmutableOrderedMultiDict
   :members: copy

.. autoclass:: CombinedMultiDict

.. autoclass:: ImmutableDict
   :members: copy

.. autoclass:: ImmutableList

.. autoclass:: FileMultiDict
   :members:

.. _http-datastructures:

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
   :members: accept_html, accept_xhtml, accept_json

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

.. autoclass:: IfRange
   :members:

.. autoclass:: Range
   :members:

.. autoclass:: ContentRange
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
