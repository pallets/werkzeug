=========
Utilities
=========

.. module:: werkzeug

You can import all these objects directly from :mod:`werkzeug`.


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

.. autofunction:: uri_to_iri

.. autofunction:: iri_to_uri

.. autofunction:: extract_path_info


HTML Helpers
============

.. autoclass:: HTMLBuilder

.. autofunction:: escape

.. autofunction:: unescape


General Helpers
===============

.. autoclass:: UserAgent
   :members:

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


Security Helpers
================

.. versionadded:: 0.6.1

.. autofunction:: generate_password_hash

.. autofunction:: check_password_hash
