WSGI Helpers
============

.. module:: werkzeug.wsgi

The following classes and functions are designed to make working with
the WSGI specification easier or operate on the WSGI layer. All the
functionality from this module is available on the high-level
:doc:`/wrappers`.


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

The values in HTTP requests come in as bytes representing (or encoded
to) ASCII. The WSGI specification (:pep:`3333`) decided to always use
the ``str`` type to represent values. To accomplish this, the raw bytes
are decoded using the ISO-8859-1 charset to produce a string.

Strings in the WSGI environment are restricted to ISO-8859-1 code
points. If a string read from the environment might contain characters
outside that charset, it must first be decoded to bytes as ISO-8859-1,
then encoded to a string using the proper charset (typically UTF-8). The
reverse is done when writing to the environ. This is known as the "WSGI
encoding dance".

Werkzeug provides functions to deal with this automatically so that you
don't need to be aware of the inner workings. Use the functions on this
page as well as :func:`~werkzeug.datastructures.EnvironHeaders` to read
data out of the WSGI environment.

Applications should avoid manually creating or modifying a WSGI
environment unless they take care of the proper encoding or decoding
step. All high level interfaces in Werkzeug will apply the encoding and
decoding as necessary.


Raw Request URI and Path Encoding
---------------------------------

The ``PATH_INFO`` in the environ is the path value after
percent-decoding. For example, the raw path ``/hello%2fworld`` would
show up from the WSGI server to Werkzeug as ``/hello/world``. This loses
the information that the slash was a raw character as opposed to a path
separator.

The WSGI specification (:pep:`3333`) does not provide a way to get the
original value, so it is impossible to route some types of data in the
path. The most compatible way to work around this is to send problematic
data in the query string instead of the path.

However, many WSGI servers add a non-standard environ key with the raw
path. To match this behavior, Werkzeug's test client and development
server will add the raw value to both the ``REQUEST_URI`` and
``RAW_URI`` keys. If you want to route based on this value, you can use
middleware to replace ``PATH_INFO`` in the environ before it reaches the
application. However, keep in mind that these keys are non-standard and
not guaranteed to be present.
