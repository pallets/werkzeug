===========
Middlewares
===========

.. module:: werkzeug.wsgi

Middlewares wrap applications to dispatch between them or provide
additional request handling.  Additionally to the middlewares documented
here, there is also the :class:`DebuggedApplication` class that is
implemented as a WSGI middleware.

.. autoclass:: SharedDataMiddleware
   :members: is_allowed

.. autoclass:: DispatcherMiddleware

Also there's the …

.. autofunction:: werkzeug._internal._easteregg
