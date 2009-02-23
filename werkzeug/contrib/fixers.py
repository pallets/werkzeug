# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.fixers
    ~~~~~~~~~~~~~~~~~~~~~~~

    .. versionadded:: 0.5

    This module includes various helpers that fix bugs in web servers.  They may
    be necessary for some versions of a buggy web server but not others.  We try
    to stay updated with the status of the bugs as good as possible but you have
    to make sure whether they fix the problem you encounter.

    If you notice bugs in webservers not fixed in this module consider
    contributing a patch.

    :copyright: Copyright 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from urllib import unquote


class LighttpdCGIRootFix(object):
    """Wrap the application in this middleware if you are using lighttpd
    with FastCGI or CGI and the application is mounted on the URL root.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['PATH_INFO'] = environ.get('SCRIPT_NAME', '') + \
                               environ.get('PATH_INFO', '')
        environ['SCRIPT_NAME'] = ''
        return self.app(environ, start_response)


class PathInfoFromRequestUriFix(object):
    """On windows environment variables are limited to the system charset
    which makes it impossible to store the `PATH_INFO` variable in the
    environment without loss of information on some systems.

    This is for example a problem for CGI scripts on a Windows Apache.

    This fixer works by recreating the `PATH_INFO` from `REQUEST_URI`,
    `REQUEST_URL`, or `UNENCODED_URL` (whatever is available).  Thus the
    fix can only be applied if the webserver supports either of these
    variables.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        for key in 'REQUEST_URL', 'REQUEST_URI', 'UNENCODED_URL':
            if key not in environ:
                continue
            request_uri = unquote(environ[key])
            script_name = unquote(environ.get('SCRIPT_NAME', ''))
            if request_uri.startswith(script_name):
                environ['PATH_INFO'] = request_uri[len(script_name):] \
                    .split('?', 1)[0]
                break
        return self.app(environ, start_response)


class ProxyFix(object):
    """This middleware can be applied to add HTTP proxy support to an
    application that was not designed with HTTP proxies in mind.  It
    sets `REMOTE_ADDR`, `HTTP_HOST` from `X-Forwarded` headers.

    Werkzeug wrappers have builtin support for this by setting the
    :attr:`~werkzeug.BaseRequest.is_behind_proxy` attribute to `True`.

    Do not use this middleware in non-proxy setups for security reasons.

    The original values of `REMOTE_ADDR` and `HTTP_HOST` are stored in
    the WSGI environment as `werkzeug.proxy_fix.orig_remote_addr` and
    `werkzeug.proxy_fix.orig_http_host`.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        getter = environ.get
        forwarded_for = getter('HTTP_X_FORWARDED_FOR', '').split(',')
        forwarded_host = getter('HTTP_X_FORWARDED_HOST', '')
        environ.update({
            'werkzeug.proxy_fix.orig_remote_addr':  getter('REMOTE_ADDR'),
            'werkzeug.proxy_fix.orig_http_host':    getter('HTTP_HOST')
        })
        if forwarded_for:
            environ['REMOTE_ADDR'] = forwarded_for[0].strip()
        if forwarded_host:
            environ['HTTP_HOST'] = forwarded_host
        return self.app(environ, start_response)
