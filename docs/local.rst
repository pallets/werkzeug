Context Locals
==============

.. module:: werkzeug.local

You may find that you have some data during each request that you want
to use across functions. Instead of passing these as arguments between
every function, you may want to access them as global data. However,
using global variables in Python web applications is not thread safe;
different workers might interfere with each others' data.

Instead of storing common data during a request using global variables,
you must use context-local variables instead. A context local is
defined/imported globally, but the data it contains is specific to the
current thread, asyncio task, or greenlet. You won't accidentally get
or overwrite another worker's data.

The current approach for storing per-context data in Python is the
:class:`contextvars` module. Context vars store data per thread, async
task, or greenlet. This replaces the older :class:`threading.local`
which only handled threads.

Werkzeug provides wrappers around :class:`~contextvars.ContextVar` to
make it easier to work with.


Proxy Objects
=============

:class:`LocalProxy` allows treating a context var as an object directly
instead of needing to use and check
:meth:`ContextVar.get() <contextvars.ContextVar.get>`. If the context
var is set, the local proxy will look and behave like the object the var
is set to. If it's not set, a ``RuntimeError`` is raised for most
operations.

.. code-block:: python

    from contextvars import ContextVar
    from werkzeug.local import LocalProxy

    _request_var = ContextVar("request")
    request = LocalProxy(_request_var)

    from werkzeug.wrappers import Request

    @Request.application
    def app(r):
        _request_var.set(r)
        check_auth()
        ...

    from werkzeug.exceptions import Unauthorized

    def check_auth():
        if request.form["username"] != "admin":
            raise Unauthorized()

Accessing ``request`` will point to the specific request that each
server worker is handling. You can treat ``request`` just like an actual
``Request`` object.

``bool(proxy)`` will always return ``False`` if the var is not set. If
you need access to the object directly instead of the proxy, you can get
it with the :meth:`~LocalProxy._get_current_object` method.

.. autoclass:: LocalProxy
    :members: _get_current_object


Stacks and Namespaces
=====================

:class:`~contextvars.ContextVar` stores one value at a time. You may
find that you need to store a stack of items, or a namespace with
multiple attributes. A list or dict can be used for these, but using
them as context var values requires some extra care. Werkzeug provides
:class:`LocalStack` which wraps a list, and :class:`Local` which wraps a
dict.

There is some amount of performance penalty associated with these
objects. Because lists and dicts are mutable, :class:`LocalStack` and
:class:`Local` need to do extra work to ensure data isn't shared between
nested contexts. If possible, design your application to use
:class:`LocalProxy` around a context var directly.

.. autoclass:: LocalStack
    :members: push, pop, top, __call__

.. autoclass:: Local
    :members: __call__


Releasing Data
==============

A previous implementation of ``Local`` used internal data structures
which could not be cleaned up automatically when each context ended.
Instead, the following utilities could be used to release the data.

.. warning::

    This should not be needed with the modern implementation, as the
    data in context vars is automatically managed by Python. It is kept
    for compatibility for now, but may be removed in the future.

.. autoclass:: LocalManager
   :members: cleanup, make_middleware, middleware

.. autofunction:: release_local
