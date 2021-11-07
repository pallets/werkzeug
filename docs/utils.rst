=========
Utilities
=========

Various utility functions shipped with Werkzeug.

.. module:: werkzeug.utils


General Helpers
===============

.. autoclass:: cached_property
   :members:

.. autoclass:: environ_property

.. autoclass:: header_property

.. autofunction:: redirect

.. autofunction:: append_slash_redirect

.. autofunction:: send_file

.. autofunction:: import_string

.. autofunction:: find_modules

.. autofunction:: secure_filename


URL Helpers
===========

Please refer to :doc:`urls`.


User Agent API
==============

.. module:: werkzeug.user_agent

.. autoclass:: UserAgent
    :members:
    :member-order: bysource


Security Helpers
================

.. module:: werkzeug.security

.. autofunction:: generate_password_hash

.. autofunction:: check_password_hash

.. autofunction:: safe_join


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
