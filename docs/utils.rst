=========
Utilities
=========

Various utility functions shipped with Werkzeug.


HTML Helpers
============

.. module:: werkzeug.utils

.. autoclass:: HTMLBuilder

.. autofunction:: escape

.. autofunction:: unescape


General Helpers
===============

.. autoclass:: cached_property
   :members:

.. autofunction:: invalidate_cached_property

.. autoclass:: environ_property

.. autoclass:: header_property

.. autofunction:: redirect

.. autofunction:: append_slash_redirect

.. autofunction:: send_file

.. autofunction:: import_string

.. autofunction:: find_modules

.. autofunction:: validate_arguments

.. autofunction:: secure_filename

.. autofunction:: bind_arguments


URL Helpers
===========

Please refer to :doc:`urls`.


User Agent API
==============

.. module:: werkzeug.user_agent

.. autoclass:: UserAgent
    :members:
    :member-order: bysource


UserAgent Parsing (deprecated)
==============================

.. module:: werkzeug.useragents

.. deprecated:: 2.0
    This module will be removed in Werkzeug 2.1. Subclass
    :class:`werkzeug.user_agent.UserAgent` to use a dedicated parser
    instead.

.. autoclass:: UserAgent
    :members:
    :inherited-members:
    :member-order: bysource


Security Helpers
================

.. module:: werkzeug.security

.. versionadded:: 0.6.1

.. autofunction:: generate_password_hash

.. autofunction:: check_password_hash

.. autofunction:: safe_str_cmp

.. autofunction:: safe_join

.. autofunction:: pbkdf2_hex

.. autofunction:: pbkdf2_bin


Logging
=======

Werkzeug uses standard Python :mod:`logging`. The logger is named
``"werkzeug"``.

.. code-block:: python

    import logging
    logger = logging.getLogger("werkzeug")

If the logger level is not set, it will be set to :data:`~logging.INFO`
on first use. If there is no handler for that level, a
:class:`~logging.StreamHandler` is added.
