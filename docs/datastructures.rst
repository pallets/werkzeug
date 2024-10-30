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

.. class:: OrderedMultiDict

    Works like a regular :class:`MultiDict` but preserves the
    order of the fields.  To convert the ordered multi dict into a
    list you can use the :meth:`items` method and pass it ``multi=True``.

    In general an :class:`OrderedMultiDict` is an order of magnitude
    slower than a :class:`MultiDict`.

    .. admonition:: note

       Due to a limitation in Python you cannot convert an ordered
       multi dict into a regular dict by using ``dict(multidict)``.
       Instead you have to use the :meth:`to_dict` method, otherwise
       the internal bucket objects are exposed.

    .. deprecated:: 3.1
        Will be removed in Werkzeug 3.2. Use ``MultiDict`` instead.

.. class:: ImmutableMultiDict

    An immutable :class:`OrderedMultiDict`.

    .. deprecated:: 3.1
        Will be removed in Werkzeug 3.2. Use ``ImmutableMultiDict`` instead.

    .. versionadded:: 0.6

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
    :inherited-members: ImmutableDictMixin, CallbackDict
    :member-order: groupwise

.. autoclass:: ResponseCacheControl
    :members:
    :inherited-members: CallbackDict
    :member-order: groupwise

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

      The filename of the file on the client. Can be a ``str``, or an
      instance of ``os.PathLike``.

   .. attribute:: name

      The name of the form field.

   .. attribute:: headers

      The multipart headers as :class:`Headers` object.  This usually contains
      irrelevant information but in combination with custom multipart requests
      the raw headers might be interesting.

      .. versionadded:: 0.6
