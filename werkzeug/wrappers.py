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
from werkzeug.http import HTTP_STATUS_CODES, Accept, CacheControl, \
     parse_accept_header, parse_cache_control_header, parse_etags, \
     parse_date, generate_etag, is_resource_modified, unquote_etag
from werkzeug.utils import MultiDict, CombinedMultiDict, FileStorage, \
     Headers, EnvironHeaders, cached_property, environ_property, \
     get_current_url, create_environ, url_encode, run_wsgi_app, get_host, \
     cookie_date, parse_cookie, dump_cookie, http_date, escape, _empty_stream


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
    is_behind_proxy = False

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
    args = cached_property(args)

    def data(self):
        """
        This reads the buffered incoming data from the client into the string.
        """
        return self.stream.read()
    data = cached_property(data)

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
    form = cached_property(form)

    def values(self):
        """combined multi dict for `args` and `form`"""
        return CombinedMultiDict([self.args, self.form])
    values = cached_property(values)

    def files(self):
        """File uploads."""
        if not hasattr(self, '_files'):
            self._load_post_data()
        return self._files
    files = cached_property(files)

    def cookies(self):
        """Stored Cookies."""
        return parse_cookie(self.environ, self.charset)
    cookies = cached_property(cookies)

    def headers(self):
        """The headers from the WSGI environ."""
        return EnvironHeaders(self.environ)
    headers = cached_property(headers)

    def accept_mimetypes(self):
        """List of mimetypes this client supports."""
        return parse_accept_header(self.environ.get('HTTP_ACCEPT'))
    accept_mimetypes = cached_property(accept_mimetypes)

    def accept_charsets(self):
        """list of charsets this client supports."""
        return parse_accept_header(self.environ.get('HTTP_ACCEPT_CHARSET'))
    accept_charsets = cached_property(accept_charsets)

    def accept_encodings(self):
        """
        List of encodings this client accepts.  Encodings in a HTTP term are
        compression encodings such as gzip.  For charsets have a look at
        `accept_charset`.
        """
        return parse_accept_header(self.environ.get('HTTP_ACCEPT_ENCODING'))
    accept_encodings = cached_property(accept_encodings)

    def accept_languages(self):
        """List of languages this client accepts."""
        return parse_accept_header(self.environ.get('HTTP_ACCEPT_LANGUAGE'))
    accept_languages = cached_property(accept_languages)

    def cache_control(self):
        """A `CacheControl` object for the incoming cache control headers."""
        cache_control = self.environ.get('HTTP_CACHE_CONTROL')
        return parse_cache_control_header(cache_control)
    cache_control = cached_property(cache_control)

    def if_match(self):
        """An object containing all the etags in the `If-Match` header."""
        return parse_etags(self.environ.get('HTTP_IF_MATCH'))
    if_match = cached_property(if_match)

    def if_none_match(self):
        """An object containing all the etags in the `If-None-Match` header."""
        return parse_etags(self.environ.get('HTTP_IF_NONE_MATCH'))
    if_none_match = cached_property(if_none_match)

    def if_modified_since(self):
        """The parsed `If-Modified-Since` header as datetime object."""
        return parse_date(self.environ.get('HTTP_IF_MODIFIED_SINCE'))
    if_modified_since = cached_property(if_modified_since)

    def if_unmodified_since(self):
        """The parsed `If-Unmodified-Since` header as datetime object."""
        return parse_date(self.environ.get('HTTP_IF_UNMODIFIED_SINCE'))
    if_unmodified_since = cached_property(if_unmodified_since)

    def path(self):
        """Requested path."""
        path = '/' + (self.environ.get('PATH_INFO') or '').lstrip('/')
        return path.decode(self.charset, 'ignore')
    path = cached_property(path)

    def script_root(self):
        """The root path of the script."""
        path = (self.environ.get('SCRIPT_NAME') or '').rstrip('/')
        return path.decode(self.charset, 'ignore')
    script_root = cached_property(script_root)

    def url(self):
        """The reconstructed current URL"""
        return get_current_url(self.environ)
    url = cached_property(url)

    def base_url(self):
        """Like `url` but without the querystring"""
        return get_current_url(self.environ, strip_querystring=True)
    base_url = cached_property(base_url)

    def url_root(self):
        """The full URL root (with hostname), this is the application root."""
        return get_current_url(self.environ, True)
    url_root = cached_property(url_root)

    def host_url(self):
        """Just the host with scheme."""
        return get_current_url(self.environ, host_only=True)
    host_url = cached_property(host_url)

    def host(self):
        """Just the host including the port if available."""
        return get_host(self.environ)
    host = cached_property(host)

    def is_secure(self):
        """True if the request is secure."""
        return self.environ['wsgi.url_scheme'] == 'https'
    is_secure = property(is_secure, doc=is_secure.__doc__)

    query_string = environ_property('QUERY_STRING', '', read_only=True)
    remote_addr = environ_property('REMOTE_ADDR', read_only=True)
    method = environ_property('REQUEST_METHOD', 'GET', read_only=True)

    def access_route(self):
        """
        If an forwarded header exists this is a list of all ip addresses
        from the client ip to the last proxy server.
        """
        if 'HTTP_X_FORWARDED_FOR' in self.environ:
            addr = self.environ['HTTP_X_FORWARDED_FOR'].split(',')
            return [x.strip() for x in addr]
        elif 'REMOTE_ADDR' in self.environ:
            return [self.environ['REMOTE_ADDR']]
        return []
    access_route = cached_property(access_route)

    def remote_addr(self):
        """The remote address of the client."""
        if self.is_behind_proxy and self.access_route:
            return self.access_route[0]
        return self.environ.get('REMOTE_ADDR')
    remote_addr = property(remote_addr)

    def is_xhr(self):
        """
        True if the request was triggered via an JavaScript XMLHttpRequest.
        This only works with libraries that support the X-Requested-With
        header and set it to "XMLHttpRequest".  Libraries that do that are
        prototype, jQuery and Mochikit.
        """
        return self.environ.get('X_REQUESTED_WITH') == 'XmlHttpRequest'
    is_xhr = property(is_xhr, doc=is_xhr.__doc__)

    is_multithread = environ_property('wsgi.multithread')
    is_multiprocess = environ_property('wsgi.multiprocess')
    is_run_once = environ_property('wsgi.run_once')


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

    def cache_control(self):
        def on_update(cache_control):
            if not cache_control and 'cache-control' in self.headers:
                del self.headers['cache-control']
            elif cache_control:
                self.headers['Cache-Control'] = cache_control.to_header()
        value = self.headers.get('Cache-Control')
        if value is not None:
            value = parse_cache_control_header(value)
        return CacheControl(value, on_update)
    cache_control = cached_property(cache_control)

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
                   path='/', domain=None, secure=None, httponly=False):
        """Set a new cookie."""
        self.headers.add('Set-Cookie', dump_cookie(key, value, max_age,
                         expires, path, domain, secure, httponly,
                         self.charset))

    def delete_cookie(self, key, path='/', domain=None):
        """Delete a cookie."""
        self.set_cookie(key, expires=0, max_age=0, path=path, domain=domain)

    def header_list(self):
        """
        This returns the headers in the target charset as list.  It's used in
        __call__ to get the headers for the response.
        """
        return self.headers.to_list(self.charset)
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
                get_current_url(environ, root_only=True),
                self.headers['Location']
            )

    def make_conditional(self, request_or_environ):
        """
        Make the response conditional to the request.  This method works best
        if an etag was defined for the response already.  The `add_etag`
        method can be used to do that.  If called without etag just the date
        header is set.

        This does nothing if the request method in the request or enviorn is
        anything but GET or HEAD.

        It does not remove the body of the response because that's something
        the `__call__` function does for us automatically.

        Returns self so that you can do ``return resp.make_conditional(req)``
        but modifies the object in-place.
        """
        environ = getattr(request_or_environ, 'environ', request_or_environ)
        if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
            return
        self.headers['Date'] = http_date()
        etag, weak = unquote_etag(self.headers.get('etag'))
        if not is_resource_modified(environ, etag, None,
                                    self.headers.get('last-modified')):
            self.status_code = 304
        return self

    def add_etag(self, overwrite=False, weak=False):
        """Add an etag for the current response if there is none yet."""
        if not overwrite and 'etag' in self.headers:
            return
        self.headers['Etag'] = generate_etag(self.response_body, weak)

    def close(self):
        """Close the wrapped response if possible."""
        if hasattr(self.response, 'close'):
            self.response.close()

    def freeze(self):
        """
        Call this method if you want to make your response object ready for
        pickeling.  This buffers the generator if there is one and sets the
        e-tag.
        """
        self.add_etag()

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


# TODO: backwards compatibility interface.  goes away with werkzeug 0.3
try:
    from werkzeug.contrib.reporterstream import BaseReporterStream
except ImportError:
    class BaseReporterStream(object):
        def __new__(*args, **kw):
            raise RuntimeError('base reporter stream is now part of the '
                               'contrib package.  In order to use it install '
                               'werkzeug with the contrib package enabled '
                               'and import it from '
                               'werkzeug.contrib.reporterstream')
else:
    class BaseReporterStream(BaseReporterStream):
        def __init__(self, environ, threshold):
            from warnings import warn
            warn(DeprecationWarning('BaseReporterStream is now part of '
                                    'the werkzeug contrib module.  Import '
                                    'it from werkzeug.contrib.reporterstream'
                                    '.  As of werkzeug 0.3 this will be'
                                    'required.'))
            super(BaseReporterStream, self).__init__(environ, threshold)
