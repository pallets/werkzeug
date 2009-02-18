==============
Context Locals
==============

.. automodule:: werkzeug


Objects
=======

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
