Unicode
=======

.. currentmodule:: werkzeug

Werkzeug uses strings internally everwhere text data is assumed, even if
the HTTP standard is not Unicode aware. Basically all incoming data is
decoded from the charset (UTF-8 by default) so that you don't work with
bytes directly. Outgoing data is encoded into the target charset.


Unicode in Python
-----------------

Imagine you have the German Umlaut ``ö``. In ASCII you cannot represent
that character, but in the ``latin-1`` and ``utf-8`` character sets you
can represent it, but they look different when encoded:

>>> "ö".encode("latin1")
b'\xf6'
>>> "ö".encode("utf-8")
b'\xc3\xb6'

An ``ö`` looks different depending on the encoding which makes it hard
to work with it as bytes. Instead, Python treats strings as Unicode text
and stores the information ``LATIN SMALL LETTER O WITH DIAERESIS``
instead of the bytes for ``ö`` in a specific encoding. The length of a
string with 1 character will be 1, where the length of the bytes might
be some other value.


Unicode in HTTP
---------------

However, the HTTP spec was written in a time where ASCII bytes were the
common way data was represented. To work around this for the modern
web, Werkzeug decodes and encodes incoming and outgoing data
automatically. Data sent from the browser to the web application is
decoded from UTF-8 bytes into a string. Data sent from the application
back to the browser is encoded back to UTF-8.


Error Handling
--------------

Functions that do internal encoding or decoding accept an ``errors``
keyword argument that is passed to :meth:`str.decode` and
:meth:`str.encode`. The default is ``'replace'`` so that errors are easy
to spot. It might be useful to set it to ``'strict'`` in order to catch
the error and report the bad data to the client.


Request and Response Objects
----------------------------

In most cases, you should stick with Werkzeug's default encoding of
UTF-8. If you have a specific reason to, you can subclass
:class:`wrappers.Request` and :class:`wrappers.Response` to change the
encoding and error handling.

.. code-block:: python

    from werkzeug.wrappers.request import Request
    from werkzeug.wrappers.response import Response

    class Latin1Request(Request):
        charset = "latin1"
        encoding_errors = "strict"

    class Latin1Response(Response):
        charset = "latin1"

The error handling can only be changed for the request. Werkzeug will
always raise errors when encoding to bytes in the response. It's your
responsibility to not create data that is not present in the target
charset. This is not an issue for UTF-8.

.. _filesystem-encoding:

The Filesystem
==============

.. versionchanged:: 0.11

Several bug reports against Werkzeug have shown that the value of
:py:func:`sys.getfilesystemencoding` cannot be trusted under traditional
UNIX systems. Usually this occurs due to a misconfigured system where
``LANG`` and similar environment variables are not set. In such cases,
Python defaults to ASCII as the filesystem encoding, a very conservative
default that is usually wrong and causes more problems than it avoids.

If Werkzeug detects it's running in a misconfigured environment, it will
assume the filesystem encoding is ``UTF-8`` and issue a warning.

See :mod:`werkzeug.filesystem`.
