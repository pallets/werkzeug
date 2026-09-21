Request and Response Objects
============================

The :class:`.Request` and :class:`.Response` classes are wrappers around the
WSGI request data and response building interface.

The :class:`.Request` class wraps the incoming WSGI ``environ`` and provides
methods to parse the headers and form data. All parsing is cached, so everything
can be accessed multiple times efficiently. This is not thread-safe, so use a
lock if you'll access a request's data from multiple threads. It's not possible
to pickle or send it to other processes.

The request data comes from the client and the server, it's not something that
makes sense to change within the application. Werkzeug tries to prevent mutation
where it can, but in general you should not modify the request.

The :class:`.Response` class provides an interface for building the WSGI
response data. Many of its attributes are header properties, which allow working
with the headers as Python types rather than raw strings. Set the attribute to
an instance of the type to set the header. If the type is a dict or
:doc:`datastructure <datastructures>`, modifying it will update the header,
although this will be less efficient compared to setting a new instance if you
modify it multiple times. Set it to ``None`` or use ``del`` to unset the header.
Each property below documents its type and what behaviors it has.


Wrapping a WSGI Application
---------------------------

A WSGI application is a Python function that takes two arguments from the server,
``environ``, and ``start_response``. ``environ`` contains the incoming request
data. To return a response, the function calls ``start_response(status, headers)``,
then returns an iterator of bytes as the body.

.. code-block:: python

    def application(
        environ: dict[str, Any],
        start_response: Callable[[str, list[tuple[str, str]]], None]
    ) -> Iterator[bytes]:
        start_response("200 OK", [])
        return [b"Hello, World!"]

This is missing a lot. It's not sending any headers, including basic things
such as ``Content-Length``. It would have to parse out values from ``environ``
to do something basic like getting a ``?name=Python`` value from the URL. You
have to encode the body to bytes even for text data.

You can wrap ``environ`` with :class:`.Request`, and use :class:`.Response` to
build the status, headers, and body.

.. code-block:: python

    from werkzeug import Request, Response

    def application(environ, start_response):
        request = Request(environ)
        response = Response(f"Hello, {request.args.get("name", "World")}!")
        return response(environ, start_response)

This can be simplified even further with the :meth:`.Request.application`
decorator. Now your function will be passed a :class:`.Request`, and will return
a :class:`.Response`. It can also raise Werkzeug's :doc:`exceptions` which will
be converted to responses.

.. code-block:: python

    from werkzeug import Request, Response

    @Request.application
    def application(request: Request) -> Response:
        return Response(f"Hello, {request.args.get("name", "World")}!")

API
---

.. module:: werkzeug.wrappers

.. autoclass:: Request
    :members:
    :inherited-members:

    .. automethod:: _get_file_stream

.. autoclass:: Response
    :members:
    :inherited-members:

    .. automethod:: __call__

    .. automethod:: _ensure_sequence
