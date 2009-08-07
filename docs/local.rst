==============
Context Locals
==============

.. module:: werkzeug

Sooner or later you have some things you want to have in every single view
or helper function or whatever.  In PHP the way to go are global
variables.  However that is not possible in WSGI applications without a
major drawback:  As soon as you operate on the global namespace your
application is not thread safe any longer.

The python standard library comes with a utility called "thread locals".
A thread local is a global object where you can put stuff in and get back
later in a thread safe way.  That means whenever you set or get an object
to / from a thread local object the thread local object checks in which
thread you are and delivers the correct value.

This however has a few disadvantages.  For example besides threads there
are other ways to handle concurrency in Python.  A very popular approach
are greenlets.  Also, whether every request gets its own thread is not
guaranteed in WSGI.  It could be that a request is reusing a thread from
before and data is left in the thread local object.

Here a simple example how you can use werkzeug.local::

    from werkzeug import Local, LocalManager

    local = Local()
    local_manager = LocalManager([local])

    def application(environ, start_response):
        local.request = request = Request(environ)
        ...

    application = local_manager.make_middleware(application)

Now what this code does is binding request to `local.request`.  Every
other piece of code executed after this assignment in the same context can
safely access local.request and will get the same request object.  The
`make_middleware` method on the local manager ensures that everything is
cleaned up after the request.

The same context means the same greenlet (if you're using greenlets) in
the same thread and same process.

If a request object is not yet set on the local object and you try to
access it you will get an `AttributeError`.  You can use `getattr` to avoid
that::

    def get_request():
        return getattr(local, 'request', None)

This will try to get the request or return `None` if the request is not
(yet?) available.

Note that local objects cannot manage themselves, for that you need a local
manager.  You can pass a local manager multiple locals or add additionals
later by appending them to `manager.locals` and everytime the manager
cleans up it will clean up all the data left in the locals for this
context.

.. autoclass:: LocalManager
   :members: cleanup, make_middleware, middleware, get_ident

.. autoclass:: LocalProxy
   :members: _get_current_object

   Keep in mind that ``repr()`` is also forwarded, so if you want to find
   out if you are dealing with a proxy you can do an ``isinstance()`` check:

   .. sourcecode:: pycon

       >>> from werkzeug import LocalProxy
       >>> isinstance(request, LocalProxy)
       True

   You can also create proxy objects by hand:

   .. sourcecode:: python

       from werkzeug import Local, LocalProxy
       local = Local()
       request = LocalProxy(local, 'request')
