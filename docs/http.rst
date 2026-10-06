==============
HTTP Utilities
==============

.. module:: werkzeug.http

Werkzeug provides a couple of functions to parse and generate HTTP headers
that are useful when implementing WSGI middlewares or whenever you are
operating on a lower level layer.  All this functionality is also exposed
from request and response objects.


Datetime Functions
==================

These functions simplify working with times in an HTTP context. Werkzeug
produces timezone-aware :class:`~datetime.datetime` objects in UTC. When
passing datetime objects to Werkzeug, it assumes any naive datetime is
in UTC.

When comparing datetime values from Werkzeug, your own datetime objects
must also be timezone-aware, or you must make the values from Werkzeug
naive.

*   ``dt = datetime.now(timezone.utc)`` gets the current time in UTC.
*   ``dt = datetime(..., tzinfo=timezone.utc)`` creates a time in UTC.
*   ``dt = dt.replace(tzinfo=timezone.utc)`` makes a naive object aware
    by assuming it's in UTC.
*   ``dt = dt.replace(tzinfo=None)`` makes an aware object naive.

.. autofunction:: parse_date

.. autofunction:: http_date


Header Parsing
==============

The following functions can be used to parse incoming HTTP headers.
Because Python does not provide data structures with the semantics required
by :rfc:`2616`, Werkzeug implements some custom data structures that are
:ref:`documented separately <http-datastructures>`.

.. autofunction:: parse_options_header

.. autofunction:: parse_set_header

.. autofunction:: parse_list_header

.. autofunction:: parse_dict_header

.. autofunction:: parse_accept_header(value, [class])

.. autofunction:: parse_cache_control_header

.. autofunction:: parse_if_range_header

.. autofunction:: parse_range_header

.. autofunction:: parse_content_range_header

Header Utilities
================

The following utilities operate on HTTP headers well but do not parse
them.  They are useful if you're dealing with conditional responses or if
you want to proxy arbitrary requests but want to remove WSGI-unsupported
hop-by-hop headers.  Also there is a function to create HTTP header
strings from the parsed data.

.. autofunction:: is_entity_header

.. autofunction:: is_hop_by_hop_header

.. autofunction:: remove_entity_headers

.. autofunction:: remove_hop_by_hop_headers

.. autofunction:: is_byte_range_valid

.. autofunction:: quote_header_value

.. autofunction:: unquote_header_value

.. autofunction:: dump_header


Cookies
=======

.. autofunction:: parse_cookie

.. autofunction:: dump_cookie


Conditional Response Helpers
============================

For conditional responses the following functions might be useful:

.. autofunction:: parse_etags

.. autofunction:: quote_etag

.. autofunction:: unquote_etag

.. autofunction:: generate_etag

.. autofunction:: is_resource_modified

Constants
=========

.. data:: HTTP_STATUS_CODES

    A dict of status code -> default status message pairs.  This is used
    by the wrappers and other places where an integer status code is expanded
    to a string throughout Werkzeug.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 3.3. Use :class:`http.HTTPStatus` instead.

.. autoclass:: COEP
    :show-inheritance:
    :members:
    :undoc-members:

.. autoclass:: COOP
    :show-inheritance:
    :members:
    :undoc-members:

.. autoclass:: CORP
    :show-inheritance:
    :members:
    :undoc-members:

.. autoclass:: SecFetchSite
    :show-inheritance:
    :members:
    :undoc-members:

.. autoclass:: SecFetchMode
    :show-inheritance:
    :members:
    :undoc-members:

.. autoclass:: SecFetchDest
    :show-inheritance:
    :members:
    :undoc-members:


Form Data Parsing
=================

.. module:: werkzeug.formparser

.. autoclass:: FormDataParser

.. autofunction:: parse_form_data
