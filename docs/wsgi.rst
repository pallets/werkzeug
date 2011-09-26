============
WSGI Helpers
============

.. module:: werkzeug.wsgi

The following classes and functions are designed to make working with
the WSGI specification easier or operate on the WSGI layer.  All the
functionality from this module is available on the high-level
:ref:`Request/Response classes <wrappers>`.


Iterator / Stream Helpers
=========================

These classes and functions simplify working with the WSGI application
iterator and the input stream.

.. autoclass:: ClosingIterator

.. autoclass:: FileWrapper

.. autoclass:: LimitedStream
   :members:

.. autofunction:: make_line_iter

.. autofunction:: make_chunk_iter

.. autofunction:: wrap_file


Environ Helpers
===============

These functions operate on the WSGI environment.  They extract useful
information or perform common manipulations:

.. autofunction:: get_host

.. autofunction:: get_current_url

.. autofunction:: pop_path_info

.. autofunction:: peek_path_info

.. autofunction:: extract_path_info

Convenience Helpers
===================

.. autofunction:: responder

.. autofunction:: werkzeug.testapp.test_app
