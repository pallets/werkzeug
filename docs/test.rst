.. module:: werkzeug.test

Testing WSGI Applications
=========================


Test Client
-----------

Werkzeug provides a :class:`Client` to simulate requests to a WSGI
application without starting a server. The client has methods for making
different types of requests, as well as managing cookies across
requests.

>>> from werkzeug.test import Client
>>> from werkzeug.testapp import test_app
>>> c = Client(test_app)
>>> response = c.get("/")
>>> response.status_code
200
>>> resp.headers
Headers([('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', '6658')])
>>> response.get_data(as_text=True)
'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"...'

The client's request methods return instances of :class:`TestResponse`.
This provides extra attributes and methods on top of
:class:`~werkzeug.wrappers.Response` that are useful for testing.


Request Body
------------

By passing a dict to ``data``, the client will construct a request body
with file and form data. It will set the content type to
``application/x-www-form-urlencoded`` if there are no files, or
``multipart/form-data`` there are.

.. code-block:: python

    import io

    response = client.post(data={
        "name": "test",
        "file": (BytesIO("file contents".encode("utf8")), "test.txt")
    })

Pass a string, bytes, or file-like object to ``data`` to use that as the
raw request body. In that case, you should set the content type
appropriately. For example, to post YAML:

.. code-block:: python

    response = client.post(
        data="a: value\nb: 1\n", content_type="application/yaml"
    )

A shortcut when testing JSON APIs is to pass a dict to ``json`` instead
of using ``data``. This will automatically call ``json.dumps()`` and
set the content type to ``application/json``. Additionally, if the
app returns JSON, ``response.json`` will automatically call
``json.loads()``.

.. code-block:: python

    response = client.post("/api", json={"a": "value", "b": 1})
    obj = response.json()


Environment Builder
-------------------

:class:`EnvironBuilder` is used to construct a WSGI environ dict. The
test client uses this internally to prepare its requests. The arguments
passed to the client request methods are the same as the builder.

Sometimes, it can be useful to construct a WSGI environment manually.
An environ builder or dict can be passed to the test client request
methods in place of other arguments to use a custom environ.

.. code-block:: Python

    from werkzeug.test import EnvironBuilder
    builder = EnvironBuilder(...)
    # build an environ dict
    environ = builder.get_environ()
    # build an environ dict wrapped in a request
    request = builder.get_request()

The test client responses make this available through
:attr:`TestResponse.request` and ``response.request.environ``.


API
---

.. autoclass:: Client
    :members:
    :member-order: bysource

.. autoclass:: TestResponse
    :members:
    :member-order: bysource

.. autoclass:: EnvironBuilder
    :members:
    :member-order: bysource

.. autofunction:: create_environ

.. autofunction:: run_wsgi_app
