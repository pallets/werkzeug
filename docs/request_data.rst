Reading and Parsing Request Data
================================

Werkzeug's :class:`.Request` class provides ways to read and parse the data sent
in a request.

-   :attr:`.Request.form` and :attr:`.Request.files` will consume and parse the
    stream as HTML form data if the content type is
    ``application/x-www-form-urlencoded`` or ``multipart/form-data``.
-   :attr:`.Request.json` and :meth:`.Request.get_json` will consume and parse
    the stream as JSON if the content type is ``application/json``.
-   :attr:`.Request.data` and :attr:`.Request.get_data` will consume the stream
    and return the raw bytes. However, ``data`` will be empty if it was actually
    form data, and ``form`` and ``files`` will be populated instead.

All of these read from :attr:`.Request.stream`, which can only be consumed once.
However, all of these cache their data by default, so they can be accessed
multiple times even though the stream remains consumed.

If you access these then try to read ``stream``, it will be empty. If you read
from ``stream`` before accessing these, they will only see the remaining data,
and then ``stream`` will be empty.

If your application handles request data other than HTML forms or JSON, you can
subclass :class:`.Request` and add your own properties or methods that read and
parse ``stream``.


Limiting Request Data
---------------------

The :class:`Request` class provides a few attributes to control how much data is
processed from the request body. This can help mitigate DoS attacks that craft
the request in such a way that the server uses too many resources to handle it.
Each of these limits will raise a :exc:`.RequestEntityTooLarge` if they are
exceeded.

-   :attr:`~Request.max_content_length` - Stop reading data after this many
    bytes. This amount of memory, plus additional object overhead, could be used
    during one request. It's better to configure this in the WSGI server or HTTP
    server, rather than the WSGI application, which is why it's not set by
    default. Not setting it anywhere would be an issue with that application,
    not with Werkzeug.
-   :attr:`~Request.max_form_memory_size` - Stop parsing ``multipart/form-data``
    if any non-file part is larger than this number of bytes. File parts can
    be larger, they are moved to disk at this limit. The default is 500kB. This
    is an additional check, it does not replace ``max_content_length``.
-   :attr:`~Request.max_form_parts` - Stop parsing ``multipart/form-data`` if
    more than this number of parts are received. This is useful to stop a very
    large number of very small fields, especially files. The default is 1000.
    This is an additional check, it does not replace ``max_content_length``.

Each of these values can be set on the ``Request`` class to affect the default
for all requests, or on a ``request`` instance to change the behavior for a
specific request. For example, a small limit can be set by default, and a large
limit can be set on an endpoint that accepts video uploads. These values should
be tuned to the specific needs of your application and endpoints.

If not using ``Request``, use :func:`.get_input_stream` to apply
``max_content_length``, and :class:`.FormDataParser` to apply
``max_form_memory_size`` and ``max_form_parts``.

Using Werkzeug to set these limits is only one layer of protection. WSGI servers
and HTTPS servers should set their own limits on size and timeouts. The
operating system or container manager should set limits on memory and processing
time for server processes.

If a 413 Content Too Large error is returned before the entire request is read,
clients may show a "connection reset" failure instead of the 413 error. This is
based on how the WSGI/HTTP server and client handle connections, it's not
something the WSGI application (Werkzeug) has control over.


WSGI Server Input Termination
-----------------------------

The raw WSGI input stream (``environ["wsgi.input"]``) is not safe to read
directly for a number of reasons. While not part of the WSGI spec, it is widely
accepted that the WSGI server should handle waiting for available data,
buffering, and detect EOF or end of chunked input to terminate the stream. The
WSGI server indicates that it does this by setting
``environ["wsgi.input_terminated"] = True``. Otherwise, Werkzeug will only
allow reading the stream if ``Content-Length`` is set.

If the WSGI server sets ``wsgi.input_terminated``, this does not mean that the
stream is not infinite, only that it will be properly buffered and terminated if
it does end. Therefore, you must set limits as described above, or otherwise
be prepared to handle infinite streams.


Reading the Stream in Middleware
--------------------------------

When writing WSGI middleware, it is important to remember that the input stream
can only be read once. If middleware reads it, it will not be available to the
application.

Most middleware should not need to read the stream. In rare cases where it does,
you can replace the stream with what you've read to avoid this in some cases.

.. code-block:: python

    environ["wsgi.input"] = BytesIO(request.data)
    return wrapped_app(environ, start_response)

However, this will cause the entire stream to be stored in memory for the
remainder of the request. Therefore it will also not work for infinite streams.
