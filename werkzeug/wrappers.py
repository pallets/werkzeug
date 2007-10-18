# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers
    ~~~~~~~~~~~~~~~~~

    This module provides simple wrappers around `environ`,
    `start_response` and `wsgi.input`.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import cgi
import tempfile
from time import gmtime
from Cookie import SimpleCookie
from cStringIO import StringIO
from datetime import datetime
from warnings import warn

from werkzeug.constants import HTTP_STATUS_CODES
from werkzeug.utils import MultiDict, CombinedMultiDict, FileStorage, \
     Headers, lazy_property, environ_property, get_current_url


_empty_stream = StringIO('')


class _StorageHelper(cgi.FieldStorage):
    """
    Helper class used by `BaseRequest` to parse submitted file and
    form data. Don't use this class directly.
    """

    FieldStorageClass = cgi.FieldStorage

    def __init__(self, environ, get_stream):
        self.get_stream = get_stream
        cgi.FieldStorage.__init__(self,
            fp=environ['wsgi.input'],
            environ={
                'REQUEST_METHOD':   environ['REQUEST_METHOD'],
                'CONTENT_TYPE':     environ['CONTENT_TYPE'],
                'CONTENT_LENGTH':   environ['CONTENT_LENGTH']
            },
            keep_blank_values=True
        )

    def make_file(self, binary=None):
        return self.get_stream()


class BaseRequest(object):
    """
    Base Request class.
    """
    charset = 'utf-8'

    def __init__(self, environ):
        self.environ = environ
        self.environ['werkzeug.request'] = self

    def _get_file_stream(self):
        """Called to get a stream for the file upload.

        This must provide a file-like class with `read()`, `readline()`
        and `seek()` methods that is both writeable and readable."""
        return tempfile.TemporaryFile('w+b')

    def _load_post_data(self):
        """Method used internally to retrieve submitted data."""
        self._data_stream = _empty_stream
        post = []
        files = []
        if self.environ['REQUEST_METHOD'] in ('POST', 'PUT'):
            storage = _StorageHelper(self.environ, self._get_file_stream)
            self._data_stream = storage.file
            if storage.list is not None:
                for key in storage.keys():
                    values = storage[key]
                    if not isinstance(values, list):
                        values = [values]
                    for item in values:
                        if getattr(item, 'filename', None) is not None:
                            fn = item.filename.decode(self.charset, 'ignore')
                            # fix stupid IE bug (IE6 sends the whole path)
                            if fn[1:3] == ':\\':
                                fn = fn.split('\\')[-1]
                            files.append((key, FileStorage(key, fn, item.type,
                                          item.length, item.file)))
                        else:
                            post.append((key, item.value.decode(self.charset,
                                                                'ignore')))
        self._form = MultiDict(post)
        self._files = MultiDict(files)

    def read(self, *args):
        warn(DeprecationWarning('use stream.read'))
        return self._data_stream.read(*args)

    def readline(self, *args):
        warn(DeprecationWarning('use stream.readline'))
        return self._data_stream.readline(*args)

    def stream(self):
        """The stream."""
        return self._data_stream
    stream = property(stream, doc=stream.__doc__)

    def args(self):
        """URL parameters"""
        items = []
        qs = self.environ.get('QUERY_STRING', '')
        for key, values in cgi.parse_qs(qs, True).iteritems():
            for value in values:
                value = value.decode(self.charset, 'ignore')
                items.append((key, value))
        return MultiDict(items)
    args = lazy_property(args)

    def data(self):
        """
        This reads the buffered incoming data from the client into the string.
        """
        if not hasattr(self, '_data_stream'):
            self._load_post_data()
        return self._data_stream.read()
    data = lazy_property(data)

    def form(self):
        """form parameters."""
        if not hasattr(self, '_form'):
            self._load_post_data()
        return self._form
    form = lazy_property(form)

    def values(self):
        """combined multi dict for `args` and `form`"""
        return CombinedMultiDict([self.args, self.form])
    values = lazy_property(values)

    def files(self):
        """File uploads."""
        if not hasattr(self, '_files'):
            self._load_post_data()
        return self._files
    files = lazy_property(files)

    def cookies(self):
        """Stored Cookies."""
        cookie = SimpleCookie()
        cookie.load(self.environ.get('HTTP_COOKIE', ''))
        result = {}
        for key, value in cookie.iteritems():
            result[key] = value.value.decode(self.charset, 'ignore')
        return result
    cookies = lazy_property(cookies)

    def method(self):
        """Request method."""
        return self.environ['REQUEST_METHOD']
    method = property(method, doc=method.__doc__)

    def path(self):
        """Requested path."""
        path = '/' + (self.environ.get('PATH_INFO') or '').lstrip('/')
        return path.decode(self.charset, 'ignore')
    path = lazy_property(path)

    def script_root(self):
        """The root path of the script."""
        path = (self.environ.get('SCRIPT_NAME') or '').rstrip('/')
        return path.decode(self.charset, 'ignore')
    script_root = lazy_property(script_root)

    def url(self):
        """The reconstructed current URL"""
        return get_current_url(self.environ)
    url = lazy_property(url)

    def base_url(self):
        """Like `url` but without the querystring"""
        return get_current_url(self.environ, strip_querystring=True)
    base_url = lazy_property(base_url)

    def url_root(self):
        """The full URL root (with hostname), this is the application root."""
        return get_current_url(self.environ, True)
    url_root = lazy_property(url_root)

    def host_url(self):
        """Just the host with scheme."""
        return get_current_url(self.environ, host_only=True)
    host_url = lazy_property(host_url)

    query_string = environ_property('QUERY_STRING', '', read_only=True)
    remote_addr = environ_property('REMOTE_ADDR', read_only=True)


class BaseResponse(object):
    """
    Base response class.
    """
    charset = 'utf-8'
    default_mimetype = 'text/plain'

    def __init__(self, response=None, headers=None, status=200, mimetype=None):
        if response is None:
            self.response = []
        elif isinstance(response, basestring):
            self.response = [response]
        else:
            self.response = iter(response)
        if not headers:
            self.headers = Headers()
        elif isinstance(headers, Headers):
            self.headers = headers
        else:
            self.headers = Headers(headers)
        if mimetype is None and 'Content-Type' not in self.headers:
            mimetype = self.default_mimetype
        if mimetype is not None:
            if 'charset=' not in mimetype and mimetype.startswith('text/'):
                mimetype += '; charset=' + self.charset
            self.headers['Content-Type'] = mimetype
        self.status = status
        self._cookies = None

    def write(self, value):
        """If we have a buffered response this writes to the buffer."""
        if not isinstance(self.response, list):
            raise RuntimeError('cannot write to a streamed response.')
        self.response.append(value)

    def set_cookie(self, key, value='', max_age=None, expires=None,
                   path='/', domain=None, secure=None):
        """Set a new cookie."""
        try:
            key = str(key)
        except UnicodeError:
            raise TypeError('invalid key %r' % key)
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if isinstance(value, unicode):
            value = value.encode(self.charset)
        self._cookies[key] = value
        if max_age is not None:
            self._cookies[key]['max-age'] = max_age
        if expires is not None:
            if isinstance(expires, basestring):
                self._cookies[key]['expires'] = expires
                expires = None
            elif isinstance(expires, datetime):
                expires = expires.utctimetuple()
            elif not isinstance(expires, (int, long)):
                expires = gmtime(expires)
            else:
                raise ValueError('datetime or integer required')
            month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
                     'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][expires.tm_mon - 1]
            day = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                   'Friday', 'Saturday', 'Sunday'][expires.tm_wday]
            date = '%02d-%s-%s' % (
                expires.tm_mday, month, str(expires.tm_year)[-2:]
            )
            d = '%s, %s %02d:%02d:%02d GMT' % (day, date, expires.tm_hour,
                                               expires.tm_min, expires.tm_sec)
            self._cookies[key]['expires'] = d
        if not path is None:
            self._cookies[key]['path'] = path
        if not domain is None:
            self._cookies[key]['domain'] = domain
        if not secure is None:
            self._cookies[key]['secure'] = secure

    def delete_cookie(self, key):
        """Delete a cookie."""
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if key not in self._cookies:
            self._cookies[key] = ''
        self._cookies[key]['max-age'] = 0
        self._cookies[key]['expires'] = 0

    def close(self):
        """Close the wrapped response if possible."""
        if hasattr(self.response, 'close'):
            self.response.close()

    def __call__(self, environ, start_response):
        """Process this response as WSGI application."""
        headers = self.headers.to_list(self.charset)
        if self._cookies is not None:
            for morsel in self._cookies.values():
                headers.append(('Set-Cookie', morsel.output(header='')))
        status = '%d %s' % (self.status, HTTP_STATUS_CODES[self.status])

        charset = self.charset or 'utf-8'
        start_response(status, headers)
        for item in self.response:
            if isinstance(item, unicode):
                yield item.encode(charset)
            else:
                yield str(item)


class BaseReporterStream(object):
    """
    This class can be used to wrap `wsgi.input` in order to get informed about
    changes of the stream.

    Usage::

        from random import randrange

        class ReporterStream(BaseReporterStream):

            def __init__(self, environ):
                super(ReporterStream, self).__init__(environ, 1024)
                self.transport_id = randrange(0, 100000)

            def processed(self):
                s = self.environ['my.session.service']
                s.store['upload/%s' % self.transport_id] = (self.pos, self.length)
                s.flush()


    And before accessing `request.form` or similar attributes add the stream:

        stream = ReporterStream(environ)
        environ['wsgi.input'] = stream
    """

    def __init__(self, environ, threshold):
        self.threshold = threshold
        self.length = int(environ.get('CONTENT_LENGTH') or 0)
        self.pos = 0
        self.environ = environ
        self._stream = environ['wsgi.input']

    def processed(self):
        """Called after pos has changed for threshold or a line was read."""

    def read(self, size=None):
        length = self.length
        threshold = self.threshold
        buffer = []

        if size is None:
            while self.pos < length:
                step = min(threshold, length - self.pos)
                data = self._stream.read(step)
                self.pos += step
                self.processed()
                buffer.append(data)
        else:
            read = 0
            while read < size:
                step = min(threshold, length - self.pos)
                step = min(step, size)
                data = self._stream.read(step)
                self.pos += step
                read += step
                self.processed()
                buffer.append(data)

        return ''.join(buffer)

    def readline(self, *args):
        line = self._stream.readline(*args)
        self.pos += len(line)
        self.processed()
        return line

    def readlines(self, hint=None):
        result = []
        while self.pos < self.length:
            result.append(self.readline())
        return result
