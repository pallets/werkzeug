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

`0.7`
    -   improved :func:`url_decode` and :func:`url_encode` performance.
    -   fixed an issue where the SharedDataMiddleware could cause an
        internal server error on weird paths when loading via pkg_resources.
    -   fixed an URL generation bug that caused URLs to be invalid if a
        generated component contains a colon.
    -   :func:`werkzeug.import_string` now works with partially set up
        packages properly.
    -   disabled automatic socket swiching for IPv6 on the development
        server due to problems it caused.
    -   Werkzeug no longer overrides the Date header when creating a
        conditional HTTP response.
    -   The routing system provides a method to retrieve the matching
        methods for a given path.
    -   The routing system now accepts a parameter to change the encoding
        error behaviour.
    -   The local manager can now accept custom ident functions in the
        constructor that are forwarded to the wrapped local objects.
    -   url_unquote_plus now accepts unicode strings again.
    -   fixed an issues with the filesystem session support's prune
        function and concurrent usage.
    -   fixed a problem with external URL generation discarding the port.
    -   added support for pylibmc to the Werkzeug cache abstraction layer.
    -   fixed an issue with the new multipart parser that happened when
        a linkebreak happend to be on the chunk limit.
    -   cookies are now set properly if ports are in use.  A runtime error
        is raised if one tries to set a cookie for a domain without a dot.
    -   fixed an issue with Template.from_file not working for file
        descriptors.
    -   reloader can now use inotify to track reloads.  This requires the
        pyinotify library to be installed.
    -   Werkzeug debugger can now submit to custom lodgeit installations.
    -   redirect function's status code assertion now allows 201 to be used
        as redirection code.  While it's not a real redirect, it shares
        enough with redirects for the function to still be useful.
    -   Fixed securecookie for pypy.
    -   Fixed `ValueErrors` being raised on calls to `best_match` on
        `MIMEAccept` objects when invalid user data was supplied.
    -   Deprecated `werkzeug.contrib.kickstart` and `werkzeug.contrib.testtools`
    -   URL routing now can be passed the URL arguments to keep them for
        redirects.  In the future matching on URL arguments might also be
        possible.
    -   header encoding changed from utf-8 to latin1 to support a port to
        Python 3.  Bytestrings passed to the object stay untouched which
        makes it possible to have utf-8 cookies.  This is a part where
        the Python 3 version will later change in that it will always
        operate on latin1 values.
    -   Fixed a bug in the form parser that caused the last character to
        be dropped off if certain values in multipart data is used.
    -   Multipart parser now looks at the part-individual content type
        header to override the global charset.
    -   introduced mimetype and mimetype_params attribute for the file
        storage object.
    -   changed FileStorage filename fallback logic to skip special filenames
        that Python uses for marking special files like stdin.
    -   introduced more HTTP exception classes.
    -   `call_on_close` now can be used as a decorator.
    -   support for redis as cache backend.
    -   Added `BaseRequest.scheme`.

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
    -   `CacheControl` was splitted up into :class:`RequestCacheControl`
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
