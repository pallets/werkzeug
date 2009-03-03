=========
Utilities
=========

.. module:: werkzeug

You can import all these objects directly from :mod:`werkzeug`.


Middlewares
===========

.. autoclass:: SharedDataMiddleware
   :members: is_allowed

.. autoclass:: DispatcherMiddleware


WSGI Helpers
============

.. autoclass:: ClosingIterator

.. autoclass:: FileWrapper

.. autoclass:: LimitedStream
   :members:

.. autofunction:: make_line_iter

.. autofunction:: get_host

.. autofunction:: get_current_url

.. autofunction:: responder

.. autofunction:: test_app

.. autofunction:: wrap_file

.. autofunction:: pop_path_info

.. autofunction:: peek_path_info

.. autofunction:: _easteregg


URL Helpers
===========

.. autoclass:: Href

.. autofunction:: url_decode

.. autofunction:: url_encode

.. autofunction:: url_quote

.. autofunction:: url_quote_plus

.. autofunction:: url_unquote

.. autofunction:: url_unquote_plus

.. autofunction:: url_fix


HTML Helpers
============

.. autoclass:: HTMLBuilder

.. autofunction:: escape

.. autofunction:: unescape


HTTP Helpers
============

.. autoclass:: UserAgent
   :members:

.. autofunction:: dump_header
   
.. autofunction:: cookie_date

.. autofunction:: http_date

.. autofunction:: parse_form_data

.. autofunction:: parse_etags

.. autofunction:: quote_etag

.. autofunction:: unquote_etag

.. autofunction:: generate_etag

.. autofunction:: is_resource_modified

.. autofunction:: parse_options_header

.. autofunction:: parse_set_header

.. autofunction:: parse_list_header

.. autofunction:: parse_dict_header

.. autofunction:: parse_accept_header(value, [class])

.. autofunction:: parse_cache_control_header

.. autofunction:: parse_date

.. autofunction:: parse_authorization_header

.. autofunction:: parse_www_authenticate_header

.. autofunction:: remove_entity_headers

.. autofunction:: remove_hop_by_hop_headers

.. autofunction:: is_entity_header

.. autofunction:: is_hop_by_hop_header

.. autofunction:: quote_header_value

.. autofunction:: unquote_header_value

.. data:: HTTP_STATUS_CODES

    A dict of status code -> default status message pairs.  This is used
    by the wrappers and other places where a integer status code is expanded
    to a string throughout Werkzeug.


General Helpers
===============

.. autoclass:: cached_property
   :members:

.. autoclass:: environ_property

.. autoclass:: header_property

.. autofunction:: parse_cookie

.. autofunction:: dump_cookie

.. autofunction:: redirect

.. autofunction:: append_slash_redirect

.. autofunction:: import_string

.. autofunction:: find_modules

.. autofunction:: validate_arguments

.. autofunction:: secure_filename

.. autofunction:: bind_arguments
