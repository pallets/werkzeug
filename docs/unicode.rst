.. _unicode:

=======
Unicode
=======

.. currentmodule:: werkzeug

Since early Python 2 days unicode was part of all default Python builds.  It
allows developers to write applications that deal with non-ASCII characters
in a straightforward way.  But working with unicode requires a basic knowledge
about that matter, especially when working with libraries that do not support
it.

Werkzeug uses unicode internally everywhere text data is assumed, even if the
HTTP standard is not unicode aware as it.  Basically all incoming data is
decoded from the charset specified (per default `utf-8`) so that you don't
operate on bytestrings any more.  Outgoing unicode data is then encoded into
the target charset again.

Unicode in Python
=================

In Python 2 there are two basic string types: `str` and `unicode`.  `str` may
carry encoded unicode data but it's always represented in bytes whereas the
`unicode` type does not contain bytes but charpoints.  What does this mean?
Imagine you have the German Umlaut `ö`.  In ASCII you cannot represent that
character, but in the `latin-1` and `utf-8` character sets you can represent
it, but they look differently when encoded:

>>> u'ö'.encode('latin1')
'\xf6'
>>> u'ö'.encode('utf-8')
'\xc3\xb6'

So an `ö` might look totally different depending on the encoding which makes
it hard to work with it.  The solution is using the `unicode` type (as we did
above, note the `u` prefix before the string).  The unicode type does not
store the bytes for `ö` but the information, that this is a
``LATIN SMALL LETTER O WITH DIAERESIS``.

Doing ``len(u'ö')`` will always give us the expected "1" but ``len('ö')``
might give different results depending on the encoding of ``'ö'``.

Unicode in HTTP
===============

The problem with unicode is that HTTP does not know what unicode is.  HTTP
is limited to bytes but this is not a big problem as Werkzeug decodes and
encodes for us automatically all incoming and outgoing data.  Basically what
this means is that data sent from the browser to the web application is per
default decoded from an utf-8 bytestring into a `unicode` string.  Data sent
from the application back to the browser that is not yet a bytestring is then
encoded back to utf-8.

Usually this "just works" and we don't have to worry about it, but there are
situations where this behavior is problematic.  For example the Python 2 IO
layer is not unicode aware.  This means that whenever you work with data from
the file system you have to properly decode it.  The correct way to load
a text file from the file system looks like this::

    f = file('/path/to/the_file.txt', 'r')
    try:
        text = f.decode('utf-8')    # assuming the file is utf-8 encoded
    finally:
        f.close()

There is also the codecs module which provides an open function that decodes
automatically from the given encoding.


Error Handling
==============

Functions that do internal encoding or decoding accept an ``errors``
keyword argument that is passed to :meth:`str.decode` and
:meth:`str.encode`. The default is ``'replace'`` so that errors are easy
to spot. It might be useful to set it to ``'strict'`` in order to catch
the error and report the bad data to the client.


Request and Response Objects
============================

As request and response objects usually are the central entities of Werkzeug
powered applications you can change the default encoding Werkzeug operates on
by subclassing these two classes.  For example you can easily set the
application to utf-7 and strict error handling::

    from werkzeug.wrappers import BaseRequest, BaseResponse

    class Request(BaseRequest):
        charset = 'utf-7'
        encoding_errors = 'strict'

    class Response(BaseResponse):
        charset = 'utf-7'

Keep in mind that the error handling is only customizable for all decoding
but not encoding.  If Werkzeug encounters an encoding error it will raise a
:exc:`UnicodeEncodeError`.  It's your responsibility to not create data that is
not present in the target charset (a non issue with all unicode encodings
such as utf-8).

.. _filesystem-encoding:

The Filesystem
==============

.. versionchanged:: 0.11

Up until version 0.11, Werkzeug used Python's stdlib functionality to detect
the filesystem encoding. However, several bug reports against Werkzeug have
shown that the value of :py:func:`sys.getfilesystemencoding` cannot be
trusted under traditional UNIX systems. The usual problems come from
misconfigured systems, where ``LANG`` and similar environment variables are not
set. In such cases, Python would default to ASCII as filesystem encoding, a
very conservative default that is usually wrong and causes more problems than
it avoids.

Therefore Werkzeug will force the filesystem encoding to ``UTF-8`` and issue a
warning whenever it detects that it is running under BSD or Linux, and
:py:func:`sys.getfilesystemencoding` is returning an ASCII encoding.

See also :py:mod:`werkzeug.filesystem`.
