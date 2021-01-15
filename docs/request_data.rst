Dealing with Request Data
=========================

.. currentmodule:: werkzeug

The most important rule about web development is "Do not trust the user".
This is especially true for incoming request data on the input stream.
With WSGI this is actually a bit harder than you would expect.  Because
of that Werkzeug wraps the request stream for you to save you from the
most prominent problems with it.


Missing EOF Marker on Input Stream
----------------------------------

The input stream has no end-of-file marker.  If you would call the
:meth:`~file.read` method on the `wsgi.input` stream you would cause your
application to hang on conforming servers.  This is actually intentional
however painful.  Werkzeug solves that problem by wrapping the input
stream in a special :class:`LimitedStream`.  The input stream is exposed
on the request objects as :attr:`~Request.stream`.  This one is either
an empty stream (if the form data was parsed) or a limited stream with
the contents of the input stream.


When does Werkzeug Parse?
-------------------------

Werkzeug parses the incoming data under the following situations:

-   you access either :attr:`~Request.form`, :attr:`~Request.files`,
    or :attr:`~Request.stream` and the request method was
    `POST` or `PUT`.
-   if you call :func:`parse_form_data`.

These calls are not interchangeable.  If you invoke :func:`parse_form_data`
you must not use the request object or at least not the attributes that
trigger the parsing process.

This is also true if you read from the `wsgi.input` stream before the
parsing.

**General rule:** Leave the WSGI input stream alone.  Especially in
WSGI middlewares.  Use either the parsing functions or the request
object.  Do not mix multiple WSGI utility libraries for form data
parsing or anything else that works on the input stream.


How does it Parse?
------------------

The standard Werkzeug parsing behavior handles three cases:

-   input content type was `multipart/form-data`.  In this situation the
    :class:`~Request.stream` will be empty and
    :class:`~Request.form` will contain the regular `POST` / `PUT`
    data, :class:`~Request.files` will contain the uploaded
    files as :class:`FileStorage` objects.
-   input content type was `application/x-www-form-urlencoded`.  Then the
    :class:`~Request.stream` will be empty and
    :class:`~Request.form` will contain the regular `POST` / `PUT`
    data and :class:`~Request.files` will be empty.
-   the input content type was neither of them, :class:`~Request.stream`
    points to a :class:`LimitedStream` with the input data for further
    processing.

Special note on the :attr:`~Request.get_data` method: Calling this
loads the full request data into memory.  This is only safe to do if the
:attr:`~Request.max_content_length` is set.  Also you can *either*
read the stream *or* call :meth:`~Request.get_data`.


Limiting Request Data
---------------------

To avoid being the victim of a DDOS attack you can set the maximum
accepted content length and request field sizes.  The :class:`Request`
class has two attributes for that: :attr:`~Request.max_content_length`
and :attr:`~Request.max_form_memory_size`.

The first one can be used to limit the total content length.  For example
by setting it to ``1024 * 1024 * 16`` the request won't accept more than
16MB of transmitted data.

Because certain data can't be moved to the hard disk (regular post data)
whereas temporary files can, there is a second limit you can set.  The
:attr:`~Request.max_form_memory_size` limits the size of `POST`
transmitted form data.  By setting it to ``1024 * 1024 * 2`` you can make
sure that all in memory-stored fields are not more than 2MB in size.

This however does *not* affect in-memory stored files if the
`stream_factory` used returns a in-memory file.


How to extend Parsing?
----------------------

Modern web applications transmit a lot more than multipart form data or
url encoded data. To extend the capabilities, subclass :class:`Request`
or :class:`Request` and add or extend methods.
