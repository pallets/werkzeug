==================
Werkzeug Changelog
==================

.. module:: werkzeug

This file lists all major changes in Werkzeug over the versions.
For API breaking changes have a look at :ref:`api-changes`, they
are listed there in detail.

.. include:: ../CHANGES

.. _api-changes:

API Changes
===========

`0.9`
    -   Soft-deprecated the :attr:`BaseRequest.data` and
        :attr:`BaseResponse.data` attributes and introduced new methods
        to interact with entity data.  This will allows in the future to
        make better APIs to deal with request and response entity
        bodies.  So far there is no deprecation warning but users are
        strongly encouraged to update.
    -   The :class:`Headers` and :class:`EnvironHeaders` datastructures
        are now designed to operate on unicode data.  This is a backwards
        incompatible change and was necessary for the Python 3 support.
    -   The :class:`Headers` object no longer supports in-place operations
        through the old ``linked`` method.  This has been removed without
        replacement due to changes on the encoding model.

`0.6.2`
    -   renamed the attribute `implicit_seqence_conversion` attribute of
        the request object to `implicit_sequence_conversion`.  Because
        this is a feature that is typically unused and was only in there
        for the 0.6 series we consider this a bug that does not require
        backwards compatibility support which would be impossible to
        properly implement.

`0.6`
    -   Old deprecations were removed.
    -   `cached_property.writeable` was deprecated.
    -   :meth:`BaseResponse.get_wsgi_headers` replaces the older
        `BaseResponse.fix_headers` method.  The older method stays
        around for backwards compatibility reasons until 0.7.
    -   `BaseResponse.header_list` was deprecated.  You should not
        need this function, `get_wsgi_headers` and the `to_list`
        method on the regular headers should serve as a replacement.
    -   Deprecated `BaseResponse.iter_encoded`'s charset parameter.
    -   :class:`LimitedStream` non-silent usage was deprecated.
    -   the `__repr__` of HTTP exceptions changed.  This might break
        doctests.

`0.5`
    -   Werkzeug switched away from wsgiref as library for the builtin
        webserver.
    -   The `encoding` parameter for :class:`Template`\s is now called
        `charset`.  The older one will work for another two versions
        but warn with a :exc:`DeprecationWarning`.
    -   The :class:`Client` has cookie support now which is enabled
        by default.
    -   :meth:`BaseResponse._get_file_stream` is now passed more parameters
        to make the function more useful.  In 0.6 the old way to invoke
        the method will no longer work.  To support both newer and older
        Werkzeug versions you can add all arguments to the signature and
        provide default values for each of them.
    -   :func:`url_decode` no longer supports both `&` and `;` as
        separator.  This has to be specified explicitly now.
    -   The request object is now enforced to be read-only for all
        attributes.  If your code relies on modifications of some values
        makes sure to create copies of them using the mutable counterparts!
    -   Some data structures that were only used on request objects are
        now immutable as well.  (:class:`Authorization` / :class:`Accept`
        and subclasses)
    -   `CacheControl` was split up into :class:`RequestCacheControl`
        and :class:`ResponseCacheControl`, the former being immutable.
        The old class will go away in 0.6
    -   undocumented `werkzeug.test.File` was replaced by
        :class:`FileWrapper`.
    -   it's not longer possible to pass dicts inside the `data` dict
        in :class:`Client`.  Use tuples instead.
    -   It's save to modify the return value of :meth:`MultiDict.getlist`
        and methods that return lists in the :class:`MultiDict` now.  The
        class creates copies instead of revealing the internal lists.
        However :class:`MultiDict.setlistdefault` still (and intentionally)
        returns the internal list for modifications.

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
