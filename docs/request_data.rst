.. _dealing-with-request-data:

Dealing with Request Data
=========================

.. module:: werkzeug

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
on the request objects as :attr:`~BaseRequest.stream`.  This one is either
an empty stream (if the form data was parsed) or a limited stream with
the contents of the input stream.


When does Werkzeug Parse?
-------------------------

Werkzeug parses the incoming data under the following situations:

-   you access either :attr:`~BaseRequest.form`, :attr:`~BaseRequest.files`,
    or :attr:`~BaseRequest.stream` and the request method was
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
    :class:`~BaseRequest.stream` will be empty and
    :class:`~BaseRequest.form` will contain the regular `POST` / `PUT`
    data, :class:`~BaseRequest.files` will contain the uploaded
    files as :class:`FileStorage` objects.
-   input content type was `application/x-www-form-urlencoded`.  Then the
    :class:`~BaseRequest.stream` will be empty and
    :class:`~BaseRequest.form` will contain the regular `POST` / `PUT`
    data and :class:`~BaseRequest.files` will be empty.
-   the input content type was neither of them, :class:`~BaseRequest.stream`
    points to a :class:`LimitedStream` with the input data for further
    processing.

Special note on the :attr:`~BaseRequest.get_data` method: Calling this
loads the full request data into memory.  This is only safe to do if the
:attr:`~BaseRequest.max_content_length` is set.  Also you can *either*
read the stream *or* call :meth:`~BaseRequest.get_data`.


Limiting Request Data
---------------------

To avoid being the victim of a DDOS attack you can set the maximum
accepted content length and request field sizes.  The :class:`BaseRequest`
class has two attributes for that: :attr:`~BaseRequest.max_content_length`
and :attr:`~BaseRequest.max_form_memory_size`.

The first one can be used to limit the total content length.  For example
by setting it to ``1024 * 1024 * 16`` the request won't accept more than
16MB of transmitted data.

Because certain data can't be moved to the hard disk (regular post data)
whereas temporary files can, there is a second limit you can set.  The
:attr:`~BaseRequest.max_form_memory_size` limits the size of `POST`
transmitted form data.  By setting it to ``1024 * 1024 * 2`` you can make
sure that all in memory-stored fields are not more than 2MB in size.

This however does *not* affect in-memory stored files if the
`stream_factory` used returns a in-memory file.


How to extend Parsing?
----------------------

Modern web applications transmit a lot more than multipart form data or
url encoded data.  Extending the parsing capabilities by subclassing
the :class:`BaseRequest` is simple.  The following example implements
parsing for incoming JSON data::

    from werkzeug.utils import cached_property
    from werkzeug.wrappers import Request
    from simplejson import loads

    class JSONRequest(Request):
        # accept up to 4MB of transmitted data.
        max_content_length = 1024 * 1024 * 4

        @cached_property
        def json(self):
            if self.headers.get('content-type') == 'application/json':
                return loads(self.data)
