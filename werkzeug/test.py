# -*- coding: utf-8 -*-
"""
    werkzeug.test
    ~~~~~~~~~~~~~

    This module implements a client to WSGI applications for testing.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import sys
import urlparse
from time import time
from random import random
from tempfile import TemporaryFile
from cStringIO import StringIO
from cookielib import CookieJar
from mimetypes import guess_type
from urllib2 import Request as U2Request

from werkzeug._internal import _empty_stream
from werkzeug.wrappers import BaseRequest
from werkzeug.utils import create_environ, run_wsgi_app, get_current_url, \
     url_encode, url_decode
from werkzeug.datastructures import FileMultiDict, MultiDict, CombinedMultiDict, Headers


def stream_encode_multipart(values, use_tempfile=True, threshold=1024 * 500,
                            boundary=None, charset='utf-8'):
    """Encode a dict of values (either strings or file descriptors or
    :class:`FileStorage` objects.) into a multipart encoded string stored
    in a file descriptor.
    """
    if boundary is None:
        boundary = '---------------WerkzeugFormPart_%s%s' % (time(), random())
    _closure = [StringIO(), 0, False]

    if use_tempfile:
        def write(string):
            stream, total_length, on_disk = _closure
            length = len(string)
            if on_disk or length + _closure[1] <= threshold:
                stream.write(string)
            else:
                new_stream = TemporaryFile('wb+')
                new_stream.write(stream.getvalue())
                _closure[0] = new_stream
                _closure[2] = True
            _closure[1] += length
    else:
        write = _closure[0].write

    if not isinstance(values, MultiDict):
        values = MultiDict(values)

    for key, values in values.iterlists():
        for value in values:
            write('--%s\r\nContent-Disposition: form-data; name="%s"' %
                  (boundary, key))
            reader = getattr(value, 'read', None)
            if reader is not None:
                filename = getattr(value, 'filename',
                                   getattr(value, 'name', None))
                content_type = getattr(value, 'content_type', None)
                if content_type is None:
                    content_type = filename and guess_type(filename)[0] or \
                                   'application/octet-stream'
                if filename is not None:
                    write('; filename="%s"\r\n' % filename)
                else:
                    write('\r\n')
                write('Content-Type: %s\r\n\r\n' % content_type)
                while 1:
                    chunk = reader(16384)
                    if not chunk:
                        break
                    write(chunk)
            else:
                if isinstance(value, unicode):
                    value = value.encode(charset)
                write('\r\n\r\n' + value)
            write('\r\n')
        write('--%s--\r\n' % boundary)

    _closure[0].seek(0)
    return _closure[0], _closure[1], boundary


def encode_multipart(values, boundary=None, charset='utf-8'):
    """Like `stream_encode_multipart` but returns a tuple in the form
    (``boundary``, ``data``) where data is a bytestring.
    """
    stream, length, boundary = stream_encode_multipart(
        values, use_tempfile=False, boundary=boundary, charset=charset)
    return boundary, stream.read()


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
    """A cookielib.CookieJar modified to inject and read cookie headers from
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


class EnvironBuilder(object):
    """This class can be used to conveniently create a WSGI environment
    for testing purposes.
    """

    server_protocol = 'HTTP/1.0'
    wsgi_version = (1, 0)
    request_class = BaseRequest

    def __init__(self, path='/', base_url=None, query_string=None,
                 method='GET', input_stream=None, content_type=None,
                 content_length=None, errors_stream=None, multithread=None,
                 multiprocess=None, run_once=False, headers=None,
                 environ_base=None, environ_overrides=None, charset='utf-8'):
        self.charset = charset
        self.path = path
        self.base_url = base_url
        if isinstance(query_string, basestring):
            self.query_string = query_string
        else:
            if query_string is None:
                query_string = MultiDict()
            self.args = query_string
        self.method = method
        if headers is None:
            headers = Headers()
        else:
            headers = Headers(headers)
        self.headers = headers
        self.content_type = content_type
        self.errors_stream = errors_stream
        self.multithread = multithread
        self.multiprocess = multiprocess
        self.run_once = run_once
        self.environ_base = environ_base
        self.environ_overrides = environ_overrides
        self.input_stream = input_stream

    def _get_base_url(self):
        return urlparse.urlunsplit((self.url_scheme, self.host,
                                    self.script_root, '', '')).rstrip('/') + '/'

    def _set_base_url(self, value):
        if value is None:
            scheme = 'http'
            netloc = 'localhost'
            scheme = 'http'
            script_root = ''
        else:
            scheme, netloc, script_root, qs, anchor = urlparse.urlsplit(value)
            if qs or anchor:
                raise ValueError('base url must not contain a query string '
                                 'or fragment')
        self.script_root = script_root.rstrip('/')
        self.host = netloc
        self.url_scheme = scheme

    base_url = property(_get_base_url, _set_base_url)
    del _get_base_url, _set_base_url

    def _get_content_type(self):
        ct = self.headers.get('Content-Type')
        if ct is None:
            if self.method in ('POST', 'PUT'):
                if self.files:
                    return 'multipart/form-data'
                return 'application/x-www-form-urlencoded'
            return None
        return ct

    def _set_content_type(self, value):
        if value is None:
            self.headers.pop('Content-Type', None)
        else:
            self.headers['Content-Type'] = value

    content_type = property(_get_content_type, _set_content_type)
    del _get_content_type, _set_content_type

    def _get_content_length(self):
        return self.headers.get('Content-Length', type=int)

    def _set_content_length(self, value):
        self.headers['Content-Length'] = str(value)

    content_length = property(_get_content_length, _set_content_length)
    del _get_content_length, _set_content_length

    def form_property(name, storage):
        key = '_' + name
        def getter(self):
            if self._input_stream is not None:
                raise AttributeError('an input stream is defined')
            rv = getattr(self, key)
            if rv is None:
                rv = storage()
                setattr(self, key, rv)
            return rv
        def setter(self, value):
            self._input_stream = None
            setattr(self, key, value)
        return property(getter, setter)

    form = form_property('form', MultiDict)
    files = form_property('files', FileMultiDict)
    del form_property

    def _get_input_stream(self):
        return self._input_stream

    def _set_input_stream(self, value):
        self._input_stream = value
        self._form = self._files = None

    input_stream = property(_get_input_stream, _set_input_stream)
    del _get_input_stream, _set_input_stream

    def _get_query_string(self):
        if self._query_string is None:
            if self._args is not None:
                return url_encode(self._args, charset=self.charset)
            return ''
        return self._query_string

    def _set_query_string(self, value):
        self._query_string = value
        self._args = None

    query_string = property(_get_query_string, _set_query_string)
    del _get_query_string, _set_query_string

    def _get_args(self):
        if self._query_string is not None:
            raise AttributeError('a query string is defined')
        if self._args is None:
            self._args = MultiDict()
        return self._args

    def _set_args(self, value):
        self._query_string = None
        self._args = value

    args = property(_get_args, _set_args)
    del _get_args, _set_args

    def get_request(self, cls=None):
        """Returns a request with the data."""
        if cls is None:
            cls = self.request_class
        return cls(self.get_environ())

    @property
    def server_name(self):
        return self.host.split(':', 1)[0]

    @property
    def server_port(self):
        pieces = self.host.split(':', 1)
        if len(pieces) == 2 and pieces[1].isdigit():
            return int(pieces[1])
        elif self.url_scheme == 'https':
            return 443
        return 80

    def __del__(self):
        self.close()

    def close(self):
        """Closes all files."""
        for f in self.files.itervalues():
            try:
                f.close()
            except:
                pass

    def get_environ(self):
        """Return the environ."""
        input_stream = self.input_stream
        content_length = self.content_length
        content_type = self.content_type

        if input_stream is not None:
            start_pos = input_stream.tell()
            input_stream.seek(0, 2)
            end_pos = input_stream.tell()
            input_stream.seek(start_pos)
            content_length = end_pos - start_pos
        elif content_type == 'multipart/form-data':
            values = CombinedMultiDict([self.form, self.files])
            input_stream, content_length, boundary = \
                stream_encode_multipart(values, charset=self.charset)
            content_type += '; boundary="%s"' % boundary
        elif content_type == 'application/x-www-form-urlencoded':
            values = url_encode(self.form, charset=self.charset)
            content_length = len(values)
            input_stream = StringIO(values)
        else:
            input_stream = _empty_stream

        result = {}
        if self.environ_base:
            result.update(self.environ_base)
        result.update({
            'REQUEST_METHOD':       self.method,
            'SCRIPT_NAME':          self.script_root,
            'PATH_INFO':            self.path,
            'QUERY_STRING':         self.query_string,
            'SERVER_NAME':          self.server_name,
            'SERVER_PORT':          str(self.server_port),
            'HTTP_HOST':            self.host,
            'SERVER_PROTOCOL':      self.server_protocol,
            'CONTENT_TYPE':         content_type,
            'CONTENT_LENGTH':       content_length,
            'wsgi.version':         self.wsgi_version,
            'wsgi.url_scheme':      self.url_scheme,
            'wsgi.input':           input_stream,
            'wsgi.errors':          self.errors_stream or sys.stderr,
            'wsgi.multithread':     self.multithread,
            'wsgi.multiprocess':    self.multiprocess,
            'wsgi.run_once':        self.run_once
        })
        for key, value in self.headers.to_list(self.charset):
            result['HTTP_%s' % key.upper().replace('-', '_')] = value
        if self.environ_overrides:
            result.update(self.environ_overrides)
        return result


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

        Additionally you can instantiate the
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
                        content_type = 'multipart/form-data; boundary="%s"' % \
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
