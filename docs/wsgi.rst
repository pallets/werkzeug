WSGI Helpers
============

.. module:: werkzeug.wsgi

The following classes and functions are designed to make working with
the WSGI specification easier or operate on the WSGI layer. All the
functionality from this module is available on the high-level
:ref:`Request / Response classes <wrappers>`.


Iterator / Stream Helpers
-------------------------

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
---------------

These functions operate on the WSGI environment.  They extract useful
information or perform common manipulations:

.. autofunction:: get_host

.. autofunction:: get_content_length

.. autofunction:: get_input_stream

.. autofunction:: get_current_url

.. autofunction:: get_query_string

.. autofunction:: get_script_name

.. autofunction:: get_path_info

.. autofunction:: pop_path_info

.. autofunction:: peek_path_info

.. autofunction:: extract_path_info

.. autofunction:: host_is_trusted


Convenience Helpers
-------------------

.. autofunction:: responder

.. autofunction:: werkzeug.testapp.test_app


Bytes, Strings, and Encodings
-----------------------------

The WSGI environment on Python 3 works slightly different than it does
on Python 2. Werkzeug hides the differences from you if you use the
higher level APIs.

The WSGI specification (`PEP 3333`_) decided to always use the native
``str`` type. On Python 2 this means the raw bytes are passed through
and can be decoded directly. On Python 3, however, the raw bytes are
always decoded using the ISO-8859-1 charset to produce a Unicode string.

Python 3 Unicode strings in the WSGI environment are restricted to
ISO-8859-1 code points. If a string read from the environment might
contain characters outside that charset, it must first be decoded to
bytes as ISO-8859-1, then encoded to a Unicode string using the proper
charset (typically UTF-8). The reverse is done when writing to the
environ. This is known as the "WSGI encoding dance".

Werkzeug provides functions to deal with this automatically so that you
don't need to be aware of the inner workings. Use the functions on this
page as well as :func:`~werkzeug.datastructures.EnvironHeaders` to read
data out of the WSGI environment.

Applications should avoid manually creating or modifying a WSGI
environment unless they take care of the proper encoding or decoding
step. All high level interfaces in Werkzeug will apply the encoding and
decoding as necessary.

.. _PEP 3333: https://www.python.org/dev/peps/pep-3333/#unicode-issues
