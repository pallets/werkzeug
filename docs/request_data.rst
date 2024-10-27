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

The :class:`Request` class provides a few attributes to control how much data is
processed from the request body. This can help mitigate DoS attacks that craft the
request in such a way that the server uses too many resources to handle it. Each of
these limits will raise a :exc:`~werkzeug.exceptions.RequestEntityTooLarge` if they are
exceeded.

-   :attr:`~Request.max_content_length` - Stop reading request data after this number
    of bytes. It's better to configure this in the WSGI server or HTTP server, rather
    than the WSGI application.
-   :attr:`~Request.max_form_memory_size` - Stop reading request data if any
    non-file form field is larger than this number of bytes. While file parts
    can be moved to disk, regular form field data is stored in memory only and
    could fill up memory. The default is 500kB.
-   :attr:`~Request.max_form_parts` Stop reading request data if more than this number
    of parts are sent in multipart form data. This is useful to stop a very large number
    of very small parts, especially file parts. The default is 1000.

Each of these values can be set on the ``Request`` class to affect the default
for all requests, or on a ``request`` instance to change the behavior for a
specific request. For example, a small limit can be set by default, and a large
limit can be set on an endpoint that accepts video uploads. These values should
be tuned to the specific needs of your application and endpoints.

Using Werkzeug to set these limits is only one layer of protection. WSGI servers
and HTTPS servers should set their own limits on size and timeouts. The operating system
or container manager should set limits on memory and processing time for server
processes.

If a 413 Content Too Large error is returned before the entire request is read, clients
may show a "connection reset" failure instead of the 413 error. This is based on how the
WSGI/HTTP server and client handle connections, it's not something the WSGI application
(Werkzeug) has control over.


How to extend Parsing?
----------------------

Modern web applications transmit a lot more than multipart form data or
url encoded data. To extend the capabilities, subclass :class:`Request`
or :class:`Request` and add or extend methods.
