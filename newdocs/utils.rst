=========
Utilities
=========

.. module:: werkzeug

You can import all these objects directly from :mod:`werkzeug`.


Data Structures
===============

.. autoclass:: MultiDict
   :members:
   :inherited-members:

.. autoclass:: CombinedMultiDict

.. autoclass:: FileStorage
   :members:

   .. attribute:: stream

      The input stream for the uploaded file.  This usually points to an
      open temporary file.

   .. attribute:: filename

      The filename of the file on the client.

   .. attribute:: name

      The name of the form field.

   .. attribute:: content_type

      The content type (mimetype) of the file.

   .. attribute:: content_length

      The length of the file in bytes.

.. autoclass:: Headers([defaults])
   :members:

.. autoclass:: EnvironHeaders

.. autoclass:: Accept
   :members:

.. autoclass:: MIMEAccept
   :members: accept_html, accept_xhtml

.. autoclass:: CharsetAccept

.. autoclass:: CacheControl
   :members:

.. autoclass:: HeaderSet
   :members:

.. autoclass:: UserAgent
   :members:

.. autoclass:: ETags
   :members:

.. autoclass:: Authorization
   :members:

.. autoclass:: WWWAuthenticate
   :members:


Middlewares
===========

.. autoclass:: SharedDataMiddleware
   :members: is_allowed

.. autoclass:: DispatcherMiddleware


WSGI Helpers
============

.. autoclass:: ClosingIterator

.. autofunction:: get_host

.. autofunction:: get_current_url

.. autofunction:: responder

.. autofunction:: create_environ

.. autofunction:: run_wsgi_app

.. autofunction:: test_app


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

.. autofunction:: dump_header
   
.. autofunction:: cookie_date

.. autofunction:: http_date

.. autofunction:: parse_form_data

.. autofunction:: parse_etags

.. autofunction:: quote_etag

.. autofunction:: unquote_etag

.. autofunction:: generate_etag

.. autofunction:: is_resource_modified

.. autofunction:: parse_set_header

.. autofunction:: parse_list_header

.. autofunction:: parse_dict_header

.. autofunction:: parse_accept_header(value, [class])

.. autofunction:: parse_cache_control_header

.. autofunction:: parse_date

.. autofunction:: parse_authorization_header

.. autofunction:: parse_www_authenticate_header

.. autofunction:: remove_entity_headers


General Helpers
===============

.. autofunction:: cached_property

.. autofunction:: environ_property

.. autofunction:: header_property

.. autofunction:: parse_cookie

.. autofunction:: dump_cookie

.. autofunction:: redirect

.. autofunction:: append_slash_redirect

.. autofunction:: import_string

.. autofunction:: find_modules

.. autofunction:: validate_arguments

.. autofunction:: bind_arguments
