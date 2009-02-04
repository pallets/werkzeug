# -*- coding: utf-8 -*-
"""
    werkzeug.test
    ~~~~~~~~~~~~~

    Quite often you want to unittest your application or just check the output
    from an interactive python session.  In theory that is pretty simple because
    you can fake a WSGI environment and call the application with a dummy
    `start_response` and iterate over the application iterator but there are
    argumentably better ways to interact with an application.

    Werkzeug provides an object called `Client` which you can pass a WSGI
    application (and optionally a response wrapper) which you can use to send
    virtual requests to the application.

    A response wrapper is a callable that takes three arguments: the application
    iterator, the status and finally a list of headers.  The default response
    wrapper returns a tuple.  Because response objects have the same signature
    you can use them as response wrapper, ideally by subclassing them and hooking
    in test functionality.

    Diving In
    =========

    Werkzeug provides a `Client` object which you can pass a WSGI application (and
    optionally a response wrapper) which you can use to send virtual requests to
    the application.

    A response wrapper is a callable that takes three arguments: the application
    iterator, the status and finally a list of headers.  The default response
    wrapper returns a tuple.  Because response objects have the same signature,
    you can use them as response wrapper, ideally by subclassing them and hooking
    in test functionality.

    >>> from werkzeug import Client, BaseResponse, test_app
    >>> c = Client(test_app, BaseResponse)
    >>> resp = c.get('/')
    >>> resp.status_code
    200
    >>> resp.headers
    Headers([('Content-Type', 'text/html; charset=utf-8')])
    >>> resp.data.splitlines()[:2]
    ['<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"',
     '  "http://www.w3.org/TR/html4/loose.dtd">']

    Or without a wrapper defined:

    >>> c = Client(test_app)
    >>> app_iter, status, headers = c.get('/')
    >>> status
    '200 OK'
    >>> headers
    [('Content-Type', 'text/html; charset=utf-8')]
    >>> ''.join(app_iter).splitlines()[:2]
    ['<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"',
     '  "http://www.w3.org/TR/html4/loose.dtd">']

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from time import time
from random import random
from urllib import urlencode
from cStringIO import StringIO
from cookielib import CookieJar
from mimetypes import guess_type
from urllib2 import Request as U2Request
from werkzeug.utils import create_environ, run_wsgi_app, get_current_url


def encode_multipart(values):
    """Encode a dict of values (can either be strings or file descriptors)
    into a multipart encoded string.  The filename is taken from the `.name`
    attribute of the file descriptor.  Because StringIOs do not provide
    this attribute it will generate a random filename in that case.

    The return value is a tuple in the form (``boundary``, ``data``).

    This method does not accept unicode strings!
    """
    boundary = '-----------=_Part_%s%s' % (time(), random())
    lines = []
    for key, value in values.iteritems():
        if isinstance(value, File):
            lines.extend((
                '--' + boundary,
                'Content-Disposition: form-data; name="%s"; filename="%s"' %
                    (key, value.filename),
                'Content-Type: ' + value.mimetype,
                '',
                value.read()
            ))
        else:
            lines.extend((
                '--' + boundary,
                'Content-Disposition: form-data; name="%s"' % key,
                '',
                value
            ))
    lines.extend(('--' + boundary + '--', ''))
    return boundary, '\r\n'.join(lines)


class File(object):
    """Wraps a file descriptor or any other stream so that `encode_multipart`
    can get the mimetype and filename from it.
    """

    def __init__(self, fd, filename=None, mimetype=None):
        if isinstance(fd, basestring):
            if filename is None:
                filename = fd
            fd = file(fd, 'rb')
            try:
                self.stream = StringIO(fd.read())
            finally:
                fd.close()
        else:
            self.stream = fd
            if filename is None:
                if not hasattr(fd, 'name'):
                    raise ValueError('no filename for provided')
                filename = fd.name
        if mimetype is None:
            mimetype = guess_type(filename)[0]
        self.filename = filename
        self.mimetype = mimetype or 'application/octet-stream'

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.filename
        )


class _TestCookieHeaders(object):
    """A headers adapter for cookielib
    """

    def __init__(self, headers):
        self.headers = headers

    def getheaders(self, name):
        headers = []
        for k, v in self.headers:
            if k == name:
                headers.append(v)
        return headers


class _TestCookieResponse(object):
    """Something that looks like a httplib.HTTPResponse, but is actually just an
    adapter for our test responses to make them available for cookielib.
    """

    def __init__(self, headers):
        self.headers = _TestCookieHeaders(headers)

    def info(self):
        return self.headers


class _TestCookieJar(CookieJar):
    """A cookilib.CookiJar modified to inject and read cookie headers from
    and to wsgi environments, and wsgi application responses.
    """

    def inject_wsgi(self, environ):
        """Inject the cookies as client headers into the server's wsgi
        environment.
        """
        cvals = []
        for cookie in self:
            cvals.append('%s=%s' % (cookie.name, cookie.value))
        if cvals:
            environ['HTTP_COOKIE'] = ','.join(cvals)

    def extract_wsgi(self, environ, headers):
        """Extract the server's set-cookie headers as cookies into the
        cookie jar.
        """
        self.extract_cookies(
            _TestCookieResponse(headers),
            U2Request(get_current_url(environ)),
        )


class Client(object):
    """This class allows to send requests to a wrapped application.

    The response wrapper can be a class or factory function that takes
    three arguments: app_iter, status and headers.  The default response
    wrapper just returns a tuple.

    Example::

        class ClientResponse(BaseResponse):
            ...

        client = Client(MyApplication(), response_wrapper=ClientResponse)

    The use_cookies parameter indicates whether cookies should be stored and
    sent for subsequent requests. This is True by default, but passing False
    will disable this behaviour.

    .. versionadded:: 0.5
       `use_cookies` is new in this version.  Older versions did not provide
       builtin cookie support.
    """

    def __init__(self, application, response_wrapper=None, use_cookies=True):
        self.application = application
        if response_wrapper is None:
            response_wrapper = lambda a, s, h: (a, s, h)
        self.response_wrapper = response_wrapper
        if use_cookies:
            self.cookie_jar = _TestCookieJar()
        else:
            self.cookie_jar = None

    def open(self, path='/', base_url=None, query_string=None, method='GET',
             data=None, input_stream=None, content_type=None,
             content_length=0, errors_stream=None, multithread=False,
             multiprocess=False, run_once=False, environ_overrides=None,
             as_tuple=False, buffered=False):
        """Takes the same arguments as the `create_environ` function from the
        utility module with some additions.

        The first parameter should be the path of the request which defaults to
        '/'.  The second one can either be a absolute path (in that case the url
        host is localhost:80) or a full path to the request with scheme,
        netloc port and the path to the script.

        If the `path` contains a query string it will be used, even if the
        `query_string` parameter was given.  If it does not contain one
        the `query_string` parameter is used as querystring.  In that case
        it can either be a dict, :class:`MultiDict` or string.

        A file object for this method is either a file descriptor with an
        additional `name` attribute (like a file descriptor returned by the
        `open` / `file` function), a tuple in the form
        ``(fd, filename, mimetype)`` (all arguments except fd optional) or
        as dict with those keys and values.  They can be specified for the
        `data` argument.

        Additionally you can instanciate the
        :class:`~werkzeug.test.File` object (or a subclass of it)
        and pass it as value.

        :param method: The request method.
        :param input_stream: The input stream.  Defaults to an empty stream.
        :param data: The data you want to transmit.  You can set this to a
                     string and define a content type instead of specifying an
                     input stream.  Additionally you can pass a dict with the
                     form data.  The values could then be strings (no unicode
                     objects!) which are then URL encoded or file objects.
        :param content_type: The content type for this request.  Default is
                             an empty content type.
        :param content_length: the value for the content length header.
        :param errors_stream: the wsgi.errors stream.  Defaults to
                              `sys.stderr`.
        :param multithread: the multithreaded flag for the WSGI environment.
        :param multiprocess: the multiprocess flag for the WSGI environment.
        :param run_once: the run_once flag for the WSGI environment.
        :param buffered: set this to true to buffer the application run.
                         This will automatically close the application for
                         you as well.
        """
        if input_stream is None and data is not None and method in ('PUT', 'POST'):
            need_multipart = False
            if isinstance(data, basestring):
                assert content_type is not None, 'content type required'
            else:
                for key, value in data.iteritems():
                    if isinstance(value, basestring):
                        if isinstance(value, unicode):
                            data[key] = str(value)
                        continue
                    need_multipart = True
                    if isinstance(value, tuple):
                        data[key] = File(*value)
                    elif isinstance(value, dict):
                        data[key] = File(**value)
                    elif not isinstance(value, File):
                        data[key] = File(value)
                if need_multipart:
                    boundary, data = encode_multipart(data)
                    if content_type is None:
                        content_type = 'multipart/form-data; boundary=' + \
                            boundary
                else:
                    data = urlencode(data)
                    if content_type is None:
                        content_type = 'application/x-www-form-urlencoded'
            content_length = len(data)
            input_stream = StringIO(data)

        if hasattr(path, 'environ'):
            environ = path.environ
        elif isinstance(path, dict):
            environ = path
        else:
            environ = create_environ(path, base_url, query_string, method,
                                     input_stream, content_type, content_length,
                                     errors_stream, multithread,
                                     multiprocess, run_once)
        if environ_overrides:
            environ.update(environ_overrides)
        if self.cookie_jar is not None:
            self.cookie_jar.inject_wsgi(environ)
        rv = run_wsgi_app(self.application, environ, buffered=buffered)
        if self.cookie_jar is not None:
            self.cookie_jar.extract_wsgi(environ, rv[2])
        response = self.response_wrapper(*rv)
        if as_tuple:
            return environ, response
        return response

    def get(self, *args, **kw):
        """Like open but method is enforced to GET."""
        kw['method'] = 'GET'
        return self.open(*args, **kw)

    def post(self, *args, **kw):
        """Like open but method is enforced to POST."""
        kw['method'] = 'POST'
        return self.open(*args, **kw)

    def head(self, *args, **kw):
        """Like open but method is enforced to HEAD."""
        kw['method'] = 'HEAD'
        return self.open(*args, **kw)

    def put(self, *args, **kw):
        """Like open but method is enforced to PUT."""
        kw['method'] = 'PUT'
        return self.open(*args, **kw)

    def delete(self, *args, **kw):
        """Like open but method is enforced to DELETE."""
        kw['method'] = 'DELETE'
        return self.open(*args, **kw)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.application
        )
