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
import urlparse
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
from Cookie import SimpleCookie
from warnings import warn
from werkzeug.http import HTTP_STATUS_CODES, Accept, CacheControl, \
     parse_accept_header, parse_cache_control_header
from werkzeug.utils import MultiDict, CombinedMultiDict, FileStorage, \
     Headers, EnvironHeaders, lazy_property, environ_property, \
     get_current_url, create_environ, url_encode, run_wsgi_app, get_host, \
     cookie_date, http_date, escape, _empty_stream


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

    def __repr__(self):
        """
        A repr that doesn't read the file.  In theory that code is never
        triggered, but if we debug werkzeug itself it could be that
        werkzeug fetches the debug info for a _StorageHelper.  The default
        repr reads the whole file which causes problems in the debug view.
        """
        return '<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


class BaseRequest(object):
    """
    Base Request class.
    """
    charset = 'utf-8'

    def __init__(self, environ, populate_request=True):
        self.environ = environ
        if populate_request:
            self.environ['werkzeug.request'] = self
        self._data_stream = None

    def from_values(cls, path='/', base_url=None, query_string=None, **options):
        """
        Create a new request object based on the values provided.  If
        environ is given missing values are filled from there.  This method
        is useful for small scripts when you need to simulate a request
        from an url.  Do not use this method for unittesting, there is a
        full featured client object in `werkzeug.test` that allows to create
        multipart requests etc.
        """
        if isinstance(query_string, dict):
            query_string = url_encode(query_string, cls.charset)
        environ = options.pop('environ', None)
        new_env = create_environ(path, base_url, query_string, **options)
        result = {}
        if environ is not None:
            result.update(environ)
        result.update(new_env)
        return cls(result)
    from_values = classmethod(from_values)

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
            if storage.file:
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

    def stream(self):
        """
        The parsed stream if the submitted data was not multipart or
        urlencoded form data.
        """
        if self._data_stream is None:
            self._load_post_data()
        return self._data_stream
    stream = property(stream, doc=stream)
    input_stream = environ_property('wsgi.input', 'The WSGI input stream.')

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
        return self.stream.read()
    data = lazy_property(data)

    def form(self):
        """
        Form parameters.  Currently it's not guaranteed that the MultiDict
        returned by this function is ordered in the same way as the submitted
        form data.  The reason for this is that the underlaying cgi library
        uses a dict internally and loses the ordering.
        """
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

    def headers(self):
        """The headers from the WSGI environ."""
        return EnvironHeaders(self.environ)
    headers = lazy_property(headers)

    def accept_mimetypes(self):
        """List of mimetypes this client supports."""
        if not 'HTTP_ACCEPT' in self.environ:
            return Accept(None)
        return parse_accept_header(self.environ['HTTP_ACCEPT'])
    accept_mimetypes = lazy_property(accept_mimetypes)

    def accept_charsets(self):
        """list of charsets this client supports."""
        if not 'HTTP_ACCEPT_CHARSET' in self.environ:
            return Accept(None)
        return parse_accept_header(self.environ['HTTP_ACCEPT_CHARSET'])
    accept_charsets = lazy_property(accept_charsets)

    def accept_encodings(self):
        """
        List of encodings this client accepts.  Encodings in a HTTP term are
        compression encodings such as gzip.  For charsets have a look at
        `accept_charset`.
        """
        if not 'HTTP_ACCEPT_ENCODING' in self.environ:
            return Accept(None)
        return parse_accept_header(self.environ['HTTP_ACCEPT_ENCODING'])
    accept_encodings = lazy_property(accept_encodings)

    def accept_languages(self):
        """List of languages this client accepts."""
        if not 'HTTP_ACCEPT_LANGUAGE' in self.environ:
            return Accept(None)
        return parse_accept_header(self.environ['HTTP_ACCEPT_LANGUAGE'])
    accept_languages = lazy_property(accept_languages)

    def cache_control(self):
        """A `CacheControl` object for the incoming cache control headers."""
        if not 'HTTP_CACHE_CONTROL' in self.environ:
            return CacheControl(None)
        return parse_cache_control_header(self.environ['HTTP_CACHE_CONTROL'])

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

    def host(self):
        """Just the host including the port if available."""
        return get_host(self.environ)
    host = lazy_property(host)

    def is_secure(self):
        """True if the request is secure."""
        return self.environ['wsgi.url_scheme'] == 'https'
    is_secure = property(is_secure, doc=is_secure.__doc__)

    query_string = environ_property('QUERY_STRING', '', read_only=True)
    remote_addr = environ_property('REMOTE_ADDR', read_only=True)
    method = environ_property('REQUEST_METHOD', 'GET', read_only=True)

    def is_xhr(self):
        """
        True if the request was triggered via an JavaScript XMLHttpRequest.
        This only works with libraries that support the X-Requested-With
        header and set it to "XMLHttpRequest".  Libraries that do that are
        prototype, jQuery and Mochikit.
        """
        return self.environ.get('X_REQUESTED_WITH') == 'XmlHttpRequest'
    is_xhr = property(is_xhr, doc=is_xhr.__doc__)


class BaseResponse(object):
    """
    Base response class.
    """
    charset = 'utf-8'
    default_mimetype = 'text/plain'

    def __init__(self, response=None, status=200, headers=None, mimetype=None,
                 content_type=None):
        """
        Response can be any kind of iterable or string.  If it's a string it's
        considered being an iterable with one item which is the string passed.
        headers can be a list of tuples or a `Headers` object.

        Special note for `mimetype` and `content_type`.  For most mime types
        `mimetype` and `content_type` work the same, the difference affects
        only 'text' mimetypes.  If the mimetype passed with `mimetype` is a
        mimetype starting with `text/` it becomes a charset parameter defined
        with the charset of the response object.  In constrast the
        `content_type` parameter is always added as header unmodified.
        """
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
        if content_type is None:
            if mimetype is None and 'Content-Type' not in self.headers:
                mimetype = self.default_mimetype
            if mimetype is not None and mimetype.startswith('text/'):
                mimetype += '; charset=' + self.charset
            content_type = mimetype
        if content_type is not None:
            self.headers['Content-Type'] = content_type
        if isinstance(status, (int, long)):
            self.status_code = status
        else:
            self.status = status
        self._cookies = None
        self.cache_control = CacheControl(())
        if conditional_request is None:
            conditional_request = self.conditional_request

    def from_app(cls, app, environ, buffered=False):
        """
        Create a new response object from an application output.  This works
        best if you pass it an application that returns a generator all the
        time.  Sometimes applications may use the `write()` callable returned
        by the `start_response` function.  This tries to resolve such edge
        cases automatically.  But if you don't get the expected output you
        should set `buffered` to `True` which enforces buffering.
        """
        return cls(*run_wsgi_app(app, environ, buffered))
    from_app = classmethod(from_app)

    def _get_status_code(self):
        return int(self.status.split(None, 1)[0])
    def _set_status_code(self, code):
        self.status = '%d %s' % (code, HTTP_STATUS_CODES[code].upper())
    status_code = property(_get_status_code, _set_status_code,
                           'Get the HTTP Status code as number')
    del _get_status_code, _set_status_code

    def write(self, data):
        """If we have a buffered response this writes to the buffer."""
        if not isinstance(self.response, list):
            raise RuntimeError('cannot write to a streamed response.')
        self.response.append(data)

    def writelines(self, lines):
        """Write lines."""
        self.write(''.join(lines))

    def _get_response_body(self):
        """
        The string representation of the request body.  Whenever you access
        this property the request iterable is encoded and flattened.  This
        can lead to unwanted behavior if you stream big data.
        """
        if not isinstance(self.response, list):
            self.response = list(self.response)
        return ''.join(self.iter_encoded())
    def _set_response_body(self, value):
        """Set a new string as response body."""
        self.response = [value]
    response_body = property(_get_response_body, _set_response_body,
                             doc=_get_response_body.__doc__)
    del _get_response_body, _set_response_body

    def iter_encoded(self, charset=None):
        """
        Iter the response encoded with the encoding specified.  If no
        encoding is given the encoding from the class is used.  Note that
        this does not encode data that is already a bytestring.
        """
        charset = charset or self.charset or 'ascii'
        for item in self.response:
            if isinstance(item, unicode):
                yield item.encode(charset)
            else:
                yield str(item)

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
        if expires is not None:
            if not isinstance(expires, basestring):
                expires = cookie_date(expires)
            self._cookies[key]['expires'] = expires
        for k, v in (('path', path), ('domain', domain), ('secure', secure),
                     ('max-age', max_age)):
            if v is not None:
                self._cookies[key][k] = v

    def delete_cookie(self, key):
        """Delete a cookie."""
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if key not in self._cookies:
            self._cookies[key] = ''
        self._cookies[key]['max-age'] = 0
        self._cookies[key]['expires'] = 0

    def header_list(self):
        """
        The complete header list including headers set by the request object
        internally which are not part of the `headers` instance (such as the
        cookie headers).
        """
        headers = self.headers.to_list(self.charset)
        if self._cookies is not None:
            for morsel in self._cookies.values():
                headers.append(('Set-Cookie', morsel.output(header='')))
        if self.cache_control:
            headers.append(('Cache-Control', str(self.cache_control)))
        return headers
    header_list = property(header_list, doc=header_list.__doc__)

    def is_streamed(self):
        """
        If the request is streamed (the response is not a sequence) this
        property is `True`.
        """
        try:
            len(self.response)
        except TypeError:
            return False
        return True
    is_streamed = property(is_streamed, doc=is_streamed.__doc__)

    def fix_headers(self, environ):
        """
        This is automatically called right before the response is started
        and should fix common mistakes in headers.  For example location
        headers are joined with the root URL here.
        """
        if 'Location' in self.headers:
            self.headers['Location'] = urlparse.urljoin(
                get_current_url(environ, host_only=True),
                self.headers['Location']
            )

    def make_conditional(self, request_or_environ):
        """
        Make the response conditional to the request.  This method works best
        if an etag was defined for the response already.  The `add_etag`
        method can be used to do that.  If called without etag just the date
        header is set.

        This does nothing if the request method in the request or enviorn is
        anything but GET.
        """
        if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
            return
        environ = getattr(request_or_environ, 'environ', request_or_environ)
        self.headers['Date'] = http_date()
        if 'etag' in self.headers:
            if_none_match = environ.get('HTTP_IF_NONE_MATCH')
            last_modified = self.headers.get('last-modified')
            if_modified_since = environ.get('HTTP_IF_MODIFIED_SINCE')
            # we only set the status code because the request object removes
            # contents for 304 responses automatically on `__call__`
            if if_none_match and if_none_match == self.headers['etag'] or \
               if_modified_since == last_modified:
                self.status_code = 304

    def add_etag(self, overwrite=False):
        """Add an etag for the current response if there is none yet."""
        if not overwrite and 'etag' in self.headers:
            return
        etag = md5(self.response_body).hexdigest()
        self.headers['ETag'] = etag

    def close(self):
        """Close the wrapped response if possible."""
        if hasattr(self.response, 'close'):
            self.response.close()

    def __call__(self, environ, start_response):
        """Process this response as WSGI application."""
        self.fix_headers(environ)
        if environ['REQUEST_METHOD'] == 'HEAD':
            resp = ()
        elif 100 <= self.status_code < 200 or self.status_code in (204, 304):
            self.headers['Content-Length'] = 0
            resp = ()
        else:
            resp = self.iter_encoded()
        start_response(self.status, self.header_list)
        return resp


class BaseReporterStream(object):
    """
    This class can be used to wrap `wsgi.input` in order to get informed about
    changes of the stream.

    Usage::

        from random import randrange

        class ReporterStream(BaseReporterStream):

            def __init__(self, environ):
                super(ReporterStream, self).__init__(environ, 1024 * 16)
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
