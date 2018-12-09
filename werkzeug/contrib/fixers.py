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
import warnings

try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

from werkzeug.http import parse_options_header, parse_cache_control_header, \
    parse_set_header
from werkzeug.useragents import UserAgent
from werkzeug.datastructures import Headers, ResponseCacheControl


class CGIRootFix(object):
    """Wrap the application in this middleware if you are using FastCGI
    or CGI and you have problems with your app root being set to the CGI
    script's path instead of the path users are going to visit.

    .. versionchanged:: 0.9
        Added `app_root` parameter and renamed from
        ``LighttpdCGIRootFix``.

    :param app: the WSGI application
    :param app_root: Defaulting to ``'/'``, you can set this to
        something else if your app is mounted somewhere else.
    """

    def __init__(self, app, app_root='/'):
        self.app = app
        self.app_root = app_root.strip("/")

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = self.app_root
        return self.app(environ, start_response)


class LighttpdCGIRootFix(CGIRootFix):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "LighttpdCGIRootFix is renamed CGIRootFix and will be"
            " removed in 1.0.",
            DeprecationWarning,
            stacklevel=3,
        )
        super(LighttpdCGIRootFix, self).__init__(*args, **kwargs)


class PathInfoFromRequestUriFix(object):

    """On windows environment variables are limited to the system charset
    which makes it impossible to store the `PATH_INFO` variable in the
    environment without loss of information on some systems.

    This is for example a problem for CGI scripts on a Windows Apache.

    This fixer works by recreating the `PATH_INFO` from `REQUEST_URI`,
    `REQUEST_URL`, or `UNENCODED_URL` (whatever is available).  Thus the
    fix can only be applied if the webserver supports either of these
    variables.

    :param app: the WSGI application
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
    """Adjust the WSGI environ based on ``Forwarded`` headers that
    proxies in front of the application may set.

    When the application is running behind a server like Nginx (or
    another server or proxy), WSGI will see the request as coming from
    that server rather than the real client. Proxies set various headers
    to track where the request actually came from.

    This middleware should only be applied if the application is
    actually behind such a proxy, and should be configured with the
    number of proxies that are chained in front of it. Not all proxies
    set all the headers. Since incoming headers can be faked, you must
    set how many proxies are setting each header so the middleware knows
    what to trust.

    The original values of the headers are stored in the WSGI
    environ as ``werkzeug.proxy_fix.orig``, a dict.

    :param app: The WSGI application.
    :param x_for: Number of values to trust for ``X-Forwarded-For``.
    :param x_proto: Number of values to trust for ``X-Forwarded-Proto``.
    :param x_host: Number of values to trust for ``X-Forwarded-Host``.
    :param x_port: Number of values to trust for ``X-Forwarded-Port``.
    :param x_prefix: Number of values to trust for
        ``X-Forwarded-Prefix``.
    :param num_proxies: Deprecated, use ``x_for`` instead.

    .. versionchanged:: 0.15
        Support ``X-Forwarded-Port`` and ``X-Forwarded-Prefix``.

    .. versionchanged:: 0.15
        All headers support multiple values. The ``num_proxies``
        argument is deprecated. Each header is configured with a
        separate number of trusted proxies.

    .. versionchanged:: 0.15
        Original WSGI environ values are stored in the
        ``werkzeug.proxy_fix.orig`` dict. ``orig_remote_addr``,
        ``orig_wsgi_url_scheme``, and ``orig_http_host`` are deprecated.

    .. versionchanged:: 0.15
        ``X-Fowarded-Host`` and ``X-Forwarded-Port`` modify
        ``SERVER_NAME`` and ``SERVER_PORT``.
    """

    def __init__(
        self, app, num_proxies=None,
        x_for=1, x_proto=0, x_host=0, x_port=0, x_prefix=0
    ):
        self.app = app
        self.x_for = x_for
        self.x_proto = x_proto
        self.x_host = x_host
        self.x_port = x_port
        self.x_prefix = x_prefix
        self.num_proxies = num_proxies

    @property
    def num_proxies(self):
        """The number of proxies setting ``X-Forwarded-For`` in front
        of the application.

        .. deprecated:: 0.15
            A separate number of trusted proxies is configured for each
            header. ``num_proxies`` maps to ``x_for``.

        :internal:
        """
        warnings.warn(DeprecationWarning(
            "num_proxies is deprecated. Use x_for instead."))
        return self.x_for

    @num_proxies.setter
    def num_proxies(self, value):
        if value is not None:
            warnings.warn(DeprecationWarning(
                'num_proxies is deprecated. Use x_for instead.'))
            self.x_for = value

    def get_remote_addr(self, forwarded_for):
        """Get the real ``remote_addr`` by looking backwards ``x_for``
        number of values in the ``X-Forwarded-For`` header.

        :param forwarded_for: List of values parsed from the
            ``X-Forwarded-For`` header.
        :return: The real ``remote_addr``, or ``None`` if there were not
            at least ``x_for`` values.

        .. deprecated:: 0.15
            This is handled internally for each header.

        .. versionchanged:: 0.9
            Use ``num_proxies`` instead of always picking the first
            value.

        .. versionadded:: 0.8
        """
        warnings.warn(DeprecationWarning("get_remote_addr is deprecated."))
        return self._get_trusted_comma(self.x_for, ','.join(forwarded_for))

    def _get_trusted_comma(self, trusted, value):
        """Get the real value from a comma-separated header based on the
        configured number of trusted proxies.

        :param trusted: Number of values to trust in the header.
        :param value: Header value to parse.
        :return: The real value, or ``None`` if there are fewer values
            than the number of trusted proxies.

        .. versionadded:: 0.15
        """
        if not (trusted and value):
            return
        values = [x.strip() for x in value.split(',')]
        if len(values) >= trusted:
            return values[-trusted]

    def __call__(self, environ, start_response):
        """Modify the WSGI environ based on the various ``Forwarded``
        headers before calling the wrapped application. Store the
        original environ values in ``werkzeug.proxy_fix.orig_{key}``.
        """
        environ_get = environ.get
        orig_remote_addr = environ_get('REMOTE_ADDR')
        orig_wsgi_url_scheme = environ_get('wsgi.url_scheme')
        orig_http_host = environ_get('HTTP_HOST')
        environ.update({
            'werkzeug.proxy_fix.orig': {
                'REMOTE_ADDR': orig_remote_addr,
                'wsgi.url_scheme': orig_wsgi_url_scheme,
                'HTTP_HOST': orig_http_host,
                'SERVER_NAME': environ_get('SERVER_NAME'),
                'SERVER_PORT': environ_get('SERVER_PORT'),
                'SCRIPT_NAME': environ_get('SCRIPT_NAME'),
            },
            # todo: remove deprecated keys
            'werkzeug.proxy_fix.orig_remote_addr': orig_remote_addr,
            'werkzeug.proxy_fix.orig_wsgi_url_scheme': orig_wsgi_url_scheme,
            'werkzeug.proxy_fix.orig_http_host': orig_http_host,
        })

        x_for = self._get_trusted_comma(
            self.x_for, environ_get('HTTP_X_FORWARDED_FOR'))
        if x_for:
            environ['REMOTE_ADDR'] = x_for

        x_proto = self._get_trusted_comma(
            self.x_proto, environ_get('HTTP_X_FORWARDED_PROTO'))
        if x_proto:
            environ['wsgi.url_scheme'] = x_proto

        x_host = self._get_trusted_comma(
            self.x_host, environ_get('HTTP_X_FORWARDED_HOST'))
        if x_host:
            environ['HTTP_HOST'] = x_host
            parts = x_host.split(':', 1)
            environ['SERVER_NAME'] = parts[0]
            if len(parts) == 2:
                environ['SERVER_PORT'] = parts[1]

        x_port = self._get_trusted_comma(
            self.x_port, environ_get('HTTP_X_FORWARDED_PORT'))
        if x_port:
            host = environ.get('HTTP_HOST')
            if host:
                parts = host.split(':', 1)
                host = parts[0] if len(parts) == 2 else host
                environ['HTTP_HOST'] = '%s:%s' % (host, x_port)
            environ['SERVER_PORT'] = x_port

        x_prefix = self._get_trusted_comma(
            self.x_prefix, environ_get('HTTP_X_FORWARDED_PREFIX'))
        if x_prefix:
            environ['SCRIPT_NAME'] = x_prefix

        return self.app(environ, start_response)


class HeaderRewriterFix(object):

    """This middleware can remove response headers and add others.  This
    is for example useful to remove the `Date` header from responses if you
    are using a server that adds that header, no matter if it's present or
    not or to add `X-Powered-By` headers::

        app = HeaderRewriterFix(app, remove_headers=['Date'],
                                add_headers=[('X-Powered-By', 'WSGI')])

    :param app: the WSGI application
    :param remove_headers: a sequence of header keys that should be
                           removed.
    :param add_headers: a sequence of ``(key, value)`` tuples that should
                        be added.
    """

    def __init__(self, app, remove_headers=None, add_headers=None):
        self.app = app
        self.remove_headers = set(x.lower() for x in (remove_headers or ()))
        self.add_headers = list(add_headers or ())

    def __call__(self, environ, start_response):
        def rewriting_start_response(status, headers, exc_info=None):
            new_headers = []
            for key, value in headers:
                if key.lower() not in self.remove_headers:
                    new_headers.append((key, value))
            new_headers += self.add_headers
            return start_response(status, new_headers, exc_info)
        return self.app(environ, rewriting_start_response)


class InternetExplorerFix(object):

    """This middleware fixes a couple of bugs with Microsoft Internet
    Explorer.  Currently the following fixes are applied:

    -   removing of `Vary` headers for unsupported mimetypes which
        causes troubles with caching.  Can be disabled by passing
        ``fix_vary=False`` to the constructor.
        see: http://support.microsoft.com/kb/824847/en-us

    -   removes offending headers to work around caching bugs in
        Internet Explorer if `Content-Disposition` is set.  Can be
        disabled by passing ``fix_attach=False`` to the constructor.

    If it does not detect affected Internet Explorer versions it won't touch
    the request / response.
    """

    # This code was inspired by Django fixers for the same bugs.  The
    # fix_vary and fix_attach fixers were originally implemented in Django
    # by Michael Axiak and is available as part of the Django project:
    #     https://code.djangoproject.com/ticket/4148

    def __init__(self, app, fix_vary=True, fix_attach=True):
        self.app = app
        self.fix_vary = fix_vary
        self.fix_attach = fix_attach

    def fix_headers(self, environ, headers, status=None):
        if self.fix_vary:
            header = headers.get('content-type', '')
            mimetype, options = parse_options_header(header)
            if mimetype not in ('text/html', 'text/plain', 'text/sgml'):
                headers.pop('vary', None)

        if self.fix_attach and 'content-disposition' in headers:
            pragma = parse_set_header(headers.get('pragma', ''))
            pragma.discard('no-cache')
            header = pragma.to_header()
            if not header:
                headers.pop('pragma', '')
            else:
                headers['Pragma'] = header
            header = headers.get('cache-control', '')
            if header:
                cc = parse_cache_control_header(header,
                                                cls=ResponseCacheControl)
                cc.no_cache = None
                cc.no_store = False
                header = cc.to_header()
                if not header:
                    headers.pop('cache-control', '')
                else:
                    headers['Cache-Control'] = header

    def run_fixed(self, environ, start_response):
        def fixing_start_response(status, headers, exc_info=None):
            headers = Headers(headers)
            self.fix_headers(environ, headers, status)
            return start_response(status, headers.to_wsgi_list(), exc_info)
        return self.app(environ, fixing_start_response)

    def __call__(self, environ, start_response):
        ua = UserAgent(environ)
        if ua.browser != 'msie':
            return self.app(environ, start_response)
        return self.run_fixed(environ, start_response)
