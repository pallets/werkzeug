Data Structures
===============

.. module:: werkzeug.datastructures


MultiDict
---------

.. autoclass:: MultiDict
    :members:
    :inherited-members:

.. autoclass:: CombinedMultiDict


.. _http-datastructures:

HTTP Headers
------------

.. autoclass:: Headers
    :members:

.. autoclass:: EnvironHeaders


Structured Headers
------------------

These classes are used to parse and build specific headers for properties on
:class:`.Request` and :class:`.Response`. They all provide a ``from_header``
classmethod to create an instance by parsing the header string, and a
``to_header`` method to convert to a header string. ``bool`` can be used to test
if the instance is "empty", meaning the header value is missing or invalid. If
you need to test if the header is actually missing, look in
:attr:`.Request.headers` directly. ``to_header`` may return an empty string for
empty instances.

.. autoclass:: HeaderSet
    :members:

.. autoclass:: Accept
    :members:

.. autoclass:: MIMEAccept
    :members:

.. autoclass:: CharsetAccept

.. autoclass:: LanguageAccept

.. autoclass:: RequestCacheControl
    :members:
    :member-order: groupwise

.. autoclass:: ResponseCacheControl
    :members:
    :member-order: groupwise

.. autoclass:: Authorization
    :members:

.. autoclass:: WWWAuthenticate
    :members:

.. autoclass:: ContentSecurityPolicy
    :members:

.. autoclass:: ETag
    :members:

.. autoclass:: ETagSet
    :members:

    .. automethod:: __call__

.. autoclass:: IfRange
    :members:

.. autoclass:: Range
    :members:

.. autoclass:: ContentRange
    :members:


File Uploads
------------

.. autoclass:: FileStorage
    :members:

.. autoclass:: FileMultiDict
    :members:


Deprecated Utilities
--------------------

.. autoclass:: TypeConversionDict
    :members:

.. autoclass:: ImmutableTypeConversionDict
    :members: copy

.. autoclass:: ImmutableDict
    :members: copy

.. autoclass:: ImmutableList
