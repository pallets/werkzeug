.. _unicode:

=======
Unicode
=======

.. module:: werkzeug

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

With Werkzeug 0.3 onwards you can further control the way Werkzeug works with
unicode.  In the past Werkzeug ignored encoding errors silently on incoming
data.  This decision was made to avoid internal server errors if the user
tampered with the submitted data.  However there are situations where you
want to abort with a `400 BAD REQUEST` instead of silently ignoring the error.

All the functions that do internal decoding now accept an `errors` keyword
argument that behaves like the `errors` parameter of the builtin string method
`decode`.  The following values are possible:

`ignore`
    This is the default behavior and tells the codec to ignore characters that
    it doesn't understand silently.

`replace`
    The codec will replace unknown characters with a replacement character
    (`U+FFFD` ``REPLACEMENT CHARACTER``)

`strict`
    Raise an exception if decoding fails.

Unlike the regular python decoding Werkzeug does not raise an
:exc:`UnicodeDecodeError` if the decoding failed but an
:exc:`~exceptions.HTTPUnicodeError` which
is a direct subclass of `UnicodeError` and the `BadRequest` HTTP exception. 
The reason is that if this exception is not caught by the application but
a catch-all for HTTP exceptions exists a default `400 BAD REQUEST` error
page is displayed.

There is additional error handling available which is a Werkzeug extension
to the regular codec error handling which is called `fallback`.  Often you
want to use utf-8 but support latin1 as legacy encoding too if decoding
failed.  For this case you can use the `fallback` error handling.  For
example you can specify ``'fallback:iso-8859-15'`` to tell Werkzeug it should
try with `iso-8859-15` if `utf-8` failed.  If this decoding fails too (which
should not happen for most legacy charsets such as `iso-8859-15`) the error
is silently ignored as if the error handling was `ignore`.

Further details are available as part of the API documentation of the concrete
implementations of the functions or classes working with unicode.

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
