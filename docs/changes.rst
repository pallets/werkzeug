==================
Werkzeug Changelog
==================

.. module:: werkzeug

This file lists all major changes in Werkzeug over the versions.
For API breaking changes have a look at :ref:`api-changes`, they
are listed there in detail.

.. changelog::

.. _api-changes:

API Changes
===========

`0.5`
    -   Werkzeug switched away from wsgiref as library for the builtin
        webserver and as such the `request_handler` parameter on the
        :func:`run_simple` function is no longer supported.
    -   The `encoding` parameter for :class:`Template`\s is now called
        `charset`.  The older one will work for another two versions
        but warn with a :exc:`DeprecationWarning`.

`0.3`
    -   Werkzeug 0.3 will be the last release with Python 2.3 compatibility.
    -   The `environ_property` is now read-only by default.  This decision was
        made because the request in general should be considered read-only.

`0.2`
    -   The `BaseReporterStream` is now part of the contrib module, the
        new module is `werkzeug.contrib.reporterstream`.  Starting with
        `0.3`, the old import will not work any longer.
    -   `RequestRedirect` now uses a 301 status code.  Previously a 302
        status code was used incorrectly.  If you want to continue using
        this 302 code, use ``response = redirect(e.new_url, 302)``.
    -   `lazy_property` is now called `cached_property`.  The alias for
        the old name will disappear in Werkzeug 0.3.
    -   `match` can now raise `MethodNotAllowed` if configured for
        methods and there was no method for that request.
    -   The `response_body` attribute on the response object is now called
        `data`.  With Werkzeug 0.3 the old name will not work any longer.
    -   The file-like methods on the response object are deprecated.  If
        you want to use the response object as file like object use the
        `Response` class or a subclass of `BaseResponse` and mix the new
        `ResponseStreamMixin` class and use `response.stream`.
