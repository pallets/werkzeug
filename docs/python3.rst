.. _python3:

==============
Python 3 Notes
==============

Since version 0.9, Werkzeug supports Python 3.3+ in addition to versions 2.6
and 2.7. Older Python 3 versions such as 3.2 or 3.1 are not supported.

This part of the documentation outlines special information required to
use Werkzeug and WSGI on Python 3.

.. warning::

   Python 3 support in Werkzeug is currently highly experimental.  Please
   give feedback on it and help us improve it.


WSGI Environment
================

The WSGI environment on Python 3 works slightly different than it does on
Python 2.  For the most part Werkzeug hides the differences from you if
you work on the higher level APIs.  The main difference between Python 2
and Python 3 is that on Python 2 the WSGI environment contains bytes
whereas the environment on Python 3 contains a range of differently
encoded strings.

There are two different kinds of strings in the WSGI environ on Python 3:

-   unicode strings restricted to latin1 values.  These are used for
    HTTP headers and a few other things.
-   unicode strings carrying binary payload, roundtripped through latin1
    values.  This is usually referred as “WSGI encoding dance” throughout
    Werkzeug.

Werkzeug provides you with functionality to deal with these automatically
so that you don't need to be aware of the inner workings.  The following
functions and classes should be used to read information out of the
WSGI environment:

-   :func:`~werkzeug.wsgi.get_current_url`
-   :func:`~werkzeug.wsgi.get_host`
-   :func:`~werkzeug.wsgi.get_script_name`
-   :func:`~werkzeug.wsgi.get_path_info`
-   :func:`~werkzeug.wsgi.get_query_string`
-   :func:`~werkzeug.datastructures.EnvironHeaders`

Applications are strongly discouraged to create and modify a WSGI
environment themselves on Python 3 unless they take care of the proper
decoding step.  All high level interfaces in Werkzeug will apply the
correct encoding and decoding steps as necessary.

URLs
====

URLs in Werkzeug attempt to represent themselves as unicode strings on
Python 3.  All the parsing functions generally also provide functionality
that allow operations on bytes.  In some cases functions that deal with
URLs allow passing in `None` as charset to change the return value to byte
objects.  Internally Werkzeug will now unify URIs and IRIs as much as
possible.

Request Cleanup
===============

Request objects on Python 3 and PyPy require explicit closing when file
uploads are involved.  This is required to properly close temporary file
objects created by the multipart parser.  For that purpose the ``close()``
method was introduced.

In addition to that request objects now also act as context managers that
automatically close.
