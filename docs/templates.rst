==============
Mini Templates
==============

.. module:: werkzeug

Werkzeug ships a **minimal** templating system which is useful for small
scripts where you just want to generate some HTML and don't want another
dependency or full blown template engine system.

It it however not recommended to use this template system for anything else
than simple content generation.  The :class:`Template` class can be directly
imported from the :mod:`werkzeug` module.

.. docstring:: templates [3:-3]

The Template Class
==================

.. autoclass:: Template

   Besides the normal global functions and objects, the following functions
   are added to every namespace: `escape`, `url_encode`, `url_quote`, and
   `url_quote_plus`.  You can change those by subclassing `Template` and
   overriding the `default_context` dict::

       class MyTemplate(Template):
           default_namespace = {
               'ueber_func':       ueber_func
           }
           # Now add the old functions, too, because they are useful.
           default_namespace.update(Template.default_namespace)

   .. automethod:: from_file

   .. automethod:: render([context])
