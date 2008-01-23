# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers
    ~~~~~~~~~~~~~~~~~

    The wrappers are simple request and response objects which you can
    subclass to do whatever you want them to do.  The request object contains
    the information transmitted by the client (webbrowser) and the response
    object contains all the information sent back to the browser.

    An important detail is that the request object is created with the WSGI
    environ and will act as high-level proxy whereas the response object is an
    actual WSGI application.

    Like everything else in Werkzeug these objects will work correctly with
    unicode data.  Incoming form data parsed by the response object will be
    decoded into an unicode object if possible and if it makes sense.


    :copyright: 2007-2008 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import cgi
import tempfile
import urlparse
from datetime import datetime, timedelta
from werkzeug.http import HTTP_STATUS_CODES, Accept, CacheControl, \
     parse_accept_header, parse_cache_control_header, parse_etags, \
     parse_date, generate_etag, is_resource_modified, unquote_etag, \
     quote_etag, parse_set_header
from werkzeug.utils import MultiDict, CombinedMultiDict, FileStorage, \
     Headers, EnvironHeaders, cached_property, environ_property, \
     get_current_url, create_environ, url_encode, run_wsgi_app, get_host, \
     cookie_date, parse_cookie, dump_cookie, http_date, escape, \
     header_property, get_content_type, _empty_stream


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
    Very basic request object.  This does not implement advanced stuff like
    entity tag parsing or cache controls.  The request object is created with
    the WSGI environment as first argument and will add itself to the WSGI
    environment as ``'werkzeug.request'`` unless it's created with
    `populate_request` set to False.

    There are a couple of mixins available that add additional functionality
    to the request object, there is also a class called `Request` which
    subclasses `BaseRequest` and all the important mixins.

    It's a good idea to create a custom subclass of the `BaseRequest` and add
    missing functionality either via mixins or direct implementation.  Here
    an example for such subclasses::

        from werkzeug import BaseRequest, ETagRequestMixin

        class Request(BaseRequest, ETagRequestMixin):
            pass

    Request objects should be considered *read only*.  Even though the object
    doesn't enforce read only access everywhere you should never modify any
    data on the object itself unless you know exactly what you are doing.
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
        Create a new request object based on the values provided.  If environ
        is given missing values are filled from there.  This method is useful
        for small scripts when you need to simulate a request from an URL.  Do
        not use this method for unittesting, there is a full featured client
        object in `werkzeug.test` that allows to create multipart requests
        etc.

        This accepts the same options as the `create_environ` function from the
        utils module and additionally an `environ` parameter that can contain
        values which will override the values from dict returned by
        `create_environ`.

        Additionally a dict passed to `query_string` will be encoded in the
        request class charset.

        :return: request object
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
        """
        Called to get a stream for the file upload.

        This must provide a file-like class with `read()`, `readline()`
        and `seek()` methods that is both writeable and readable.

        The default implementation returns a temporary file.
        """
        return tempfile.TemporaryFile('w+b')

    def _load_post_data(self):
        """
        Method used internally to retrieve submitted data.  After calling
        this sets `_form` and `_files` on the request object to multi dicts
        filled with the incoming form data.  As a matter of fact the input
        stream will be empty afterwards.

        :internal:
        """
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
                            files.append((key, FileStorage(item.file, fn,
                                          key, item.type, item.length)))
                        else:
                            post.append((key, item.value.decode(self.charset,
                                                                'ignore')))
        self._form = MultiDict(post)
        self._files = MultiDict(files)

    def stream(self):
        """
        The parsed stream if the submitted data was not multipart or
        urlencoded form data.  This stream is the stream left by the CGI
        module after parsing.  This is *not* the WSGI input stream.
        """
        if self._data_stream is None:
            self._load_post_data()
        return self._data_stream
    stream = property(stream, doc=stream)
    input_stream = environ_property('wsgi.input', 'The WSGI input stream.')

    def args(self):
        """The parsed URL parameters as `MultiDict`."""
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
        Usually it's a bad idea to access `data` because a client could send
        dozens of megabytes or more to cause memory problems on the server.
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
    form = property(form, doc=form.__doc__)

    def values(self):
        """Combined multi dict for `args` and `form`"""
        return CombinedMultiDict([self.args, self.form])
    values = cached_property(values)

    def files(self):
        """
        A `MultiDict` containing all uploaded files.  Each key in
        `files` is the name from the ``<input type="file" name="" />``.  Each
        value in `files` is a Werkzeug `FieldStorage` object with the
        following members:

        - `filename` - The name of the uploaded file, as a Python string.
        - `type` - The content type of the uploaded file.
        - `data` - The raw content of the uploaded file.
        - `read()` - Read from the stream.

        Note that `files` will only contain data if the request method was POST
        and the ``<form>`` that posted to the request had
        ``enctype="multipart/form-data"``.  It will be empty otherwise.

        The files retreived will be kept in temporary files, you can store
        them somewhere else using `shutil` or the convenient `save` method on
        a `FieldStorage`.
        """
        if not hasattr(self, '_files'):
            self._load_post_data()
        return self._files
    files = property(files, doc=files.__doc__)

    def cookies(self):
        """The retreived cookie values as regular dictionary."""
        return parse_cookie(self.environ, self.charset)
    cookies = cached_property(cookies)

    def headers(self):
        """The headers from the WSGI environ as immutable `EnvironHeaders`."""
        return EnvironHeaders(self.environ)
    headers = cached_property(headers)

    def path(self):
        """
        Requested path as unicode.  This works a bit like the regular path
        info in the WSGI environment but will always include a leading slash,
        even if the URL root is accessed.
        """
        path = '/' + (self.environ.get('PATH_INFO') or '').lstrip('/')
        return path.decode(self.charset, 'ignore')
    path = cached_property(path)

    def script_root(self):
        """The root path of the script without the trailing slash."""
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
        prototype, jQuery and Mochikit and probably some more.
        """
        return self.environ.get('X_REQUESTED_WITH') == 'XmlHttpRequest'
    is_xhr = property(is_xhr, doc=is_xhr.__doc__)

    def is_secure(self):
        """True if the request is secure."""
        return self.environ['wsgi.url_scheme'] == 'https'
    is_secure = property(is_secure, doc=is_secure.__doc__)

    is_multithread = environ_property('wsgi.multithread')
    is_multiprocess = environ_property('wsgi.multiprocess')
    is_run_once = environ_property('wsgi.run_once')


class BaseResponse(object):
    """
    Base response class.  The most important fact about a response object is
    that it's a regular WSGI application.  It's initialized with a couple of
    response parameters (headers, body, status code etc.) and will start a
    valid WSGI response when called with the environ and start response
    callable.

    Because it's a WSGI application itself processing usually ends before the
    actual response is sent to the server.  This helps debugging systems
    because they can catch all the exceptions before responses are started.

    Here a small example WSGI application that takes advantage of the
    response objects::

        from werkzeug import BaseResponse as Response

        def index():
            return Response('Index page')

        def application(environ, start_response):
            path = environ.get('PATH_INFO') or '/'
            if path == '/':
                response = index()
            else:
                response = Response('Not Found', status=404)
            return response(environ, start_response)

    Like `BaseRequest` which object is lacking a lot of functionality
    implemented in mixins.  This gives you a better control about the actual
    API of your response objects, so you can create subclasses and add custom
    functionality.  A full featured response object is available as `Response`
    which implements a couple of useful mixins.

    To enforce a new type of already existing responses you can use the
    `force_type` method.  This is useful if you're working with different
    subclasses of response objects and you want to post process them with a
    know interface.
    """
    charset = 'utf-8'
    default_status = 200
    default_mimetype = 'text/plain'

    def __init__(self, response=None, status=None, headers=None,
                 mimetype=None, content_type=None):
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
            if mimetype is not None:
                mimetype = get_content_type(mimetype, self.charset)
            content_type = mimetype
        if content_type is not None:
            self.headers['Content-Type'] = content_type
        if status is None:
            status = self.default_status
        if isinstance(status, (int, long)):
            self.status_code = status
        else:
            self.status = status

    def force_type(cls, response, environ=None):
        """
        Enforce that the WSGI response is a response object of the current
        type.  Werkzeug will use the `BaseResponse` internally in many
        situations like the exceptions.  If you call `get_response` on an
        exception you will get back a regular `BaseResponse` object, even if
        you are using a custom subclass.

        This method can enforce a given response type, and it will also
        convert arbitrary WSGI callables into response objects if an environ
        is provided::

            # convert a Werkzeug response object into an instance of the
            # MyResponseClass subclass.
            response = MyResponseClass.force_type(response)

            # convert any WSGI application into a request object
            response = MyResponseClass.force_type(response, environ)

        This is especially useful if you want to post-process responses in
        the main dispatcher and use functionality provided by your subclass.

        Keep in mind that this will modify response objects in place if
        possible!
        """
        if not isinstance(response, BaseResponse):
            if environ is None:
                raise TypeError('cannot convert WSGI application into '
                                'response objects without an environ')
            response = BaseResponse(*run_wsgi_app(response, environ))
        response.__class__ = cls
        return response
    force_type = classmethod(force_type)

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
        try:
            return int(self.status.split(None, 1)[0])
        except ValueError:
            return 0
    def _set_status_code(self, code):
        try:
            self.status = '%d %s' % (code, HTTP_STATUS_CODES[code].upper())
        except KeyError:
            self.status = '%d UNKNOWN' % code
    status_code = property(_get_status_code, _set_status_code,
                           'The HTTP Status code as number')
    del _get_status_code, _set_status_code

    def write(self, data):
        """
        **deprecated**

        Use `response.stream` now, if you are using a `BaseResponse` subclass
        and mix the `ResponseStreamMixin` in.
        """
        from warnings import warn
        warn(DeprecationWarning('response.write() will go away in Werkzeug '
                                '0.3.  Use the new response.stream available '
                                'on `Response`.'))
        if not isinstance(self.response, list):
            raise RuntimeError('cannot write to a streamed response.')
        self.response.append(data)

    def writelines(self, lines):
        """
        **deprecated**

        :see: `write`
        """
        self.write(''.join(lines))

    def _get_data(self):
        """
        The string representation of the request body.  Whenever you access
        this property the request iterable is encoded and flattened.  This
        can lead to unwanted behavior if you stream big data.
        """
        if not isinstance(self.response, list):
            self.response = list(self.response)
        return ''.join(self.iter_encoded())
    def _set_data(self, value):
        self.response = [value]
    data = property(_get_data, _set_data, doc=_get_data.__doc__)

    def _deprecate_data(f):
        def proxy(*args, **kwargs):
            from warnings import warn
            warn(DeprecationWarning('response_body is now called data'))
            return f(*args, **kwargs)
        return proxy
    response_body = property(_deprecate_data(_get_data),
                             _deprecate_data(_set_data),
                             doc='**deprecated**\ncalled `data` now. '
                             'Will go away in Werkzeug 0.3')
    del _get_data, _set_data, _deprecate_data

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
        """
        Sets a cookie. The parameters are the same as in the cookie `Morsel`
        object in the Python standard library but it accepts unicode data too:

        - `max_age` should be a number of seconds, or `None` (default) if the
           cookie should last only as long as the client’s browser session.
        - `expires` should be a `datetime` object or UNIX timestamp.
        - Use `domain` if you want to set a cross-domain cookie.  For example,
          ``domain=".example.com"`` will set a cookie that is readable by the
          domain ``www.example.com``, ``foo.example.com`` etc.  Otherwise, a
          cookie will only be readable by the domain that set it.
        - `path` limits the cookie to a given path, per default it will span
          the whole domain.
        """
        self.headers.add('Set-Cookie', dump_cookie(key, value, max_age,
                         expires, path, domain, secure, httponly,
                         self.charset))

    def delete_cookie(self, key, path='/', domain=None):
        """Delete a cookie.  Fails silently if key doesn't exist."""
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
        If the response is streamed (the response is not a sequence) this
        property is `True`.  In this case streamed means that there is no
        information about the number of iterations.  This is usully `True`
        if a generator is passed to the response object.
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
        BaseResponse.data.__get__(self)

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


class AcceptMixin(object):
    """
    A mixin for classes with an `environ` attribute to get and all the HTTP
    accept headers as `Accept` objects.  This can be mixed in request objects
    or any other object that has a WSGI environ available as `environ`.
    """

    def accept_mimetypes(self):
        """List of mimetypes this client supports."""
        return parse_accept_header(self.environ.get('HTTP_ACCEPT'))
    accept_mimetypes = cached_property(accept_mimetypes)

    def accept_charsets(self):
        """List of charsets this client supports."""
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


class ETagRequestMixin(object):
    """
    Add entity tag and cache descriptors to a request object or object with
    an WSGI environment available as `environ`.  This not only provides
    access to etags but also to the cache control header.
    """

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


class UserAgentMixin(object):
    """
    Adds a `user_agent` attribute to the request object which contains the
    parsed user agent of the browser that triggered the request as `UserAgent`
    object.
    """

    def user_agent(self):
        """The current user agent."""
        from werkzeug.useragents import UserAgent
        return UserAgent(self.environ)
    user_agent = cached_property(user_agent)


class ETagResponseMixin(object):
    """
    Adds extra functionality to a response object for etag and cache
    handling.  This mixin requires an object with at least a `headers`
    object that implements a dict like interface similar to `Headers`.
    """

    def cache_control(self):
        """
        The Cache-Control general-header field is used to specify directives
        that MUST be obeyed by all caching mechanisms along the
        request/response chain.
        """
        def on_update(cache_control):
            if not cache_control and 'cache-control' in self.headers:
                del self.headers['cache-control']
            elif cache_control:
                self.headers['Cache-Control'] = cache_control.to_header()
        return parse_cache_control_header(self.headers.get('cache-control'),
                                          on_update)
    cache_control = property(cache_control, doc=cache_control.__doc__)

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
        if 'content-length' in self.headers:
            self.headers['Content-Length'] = len(self.data)
        if not is_resource_modified(environ, self.headers.get('etag'), None,
                                    self.headers.get('last-modified')):
            self.status_code = 304
        return self

    def add_etag(self, overwrite=False, weak=False):
        """Add an etag for the current response if there is none yet."""
        if overwrite or 'etag' not in self.headers:
            self.set_etag(generate_etag(self.data), weak)

    def set_etag(self, etag, weak=False):
        """Set the etag, and override the old one if there was one."""
        self.headers['ETag'] = quote_etag(etag, weak)

    def get_etag(self):
        """
        Return a tuple in the form ``(etag, is_weak)``.  If there is no
        ETag the return value is ``(None, None)``.
        """
        return unquote_etag(self.headers.get('ETag'))


class ResponseStream(object):
    """
    A file descriptor like object used by the `ResponseStreamMixin` to
    represent the body of the stream.  It directly pushes into the response
    iterable of the response object.
    """

    closed = False
    mode = 'wb'

    def __init__(self, response):
        self.response = response

    def write(self, value):
        if self.closed:
            raise ValueError('I/O operation on closed file')
        buf = self.response.response
        if not isinstance(buf, list):
            self.response.response = buf = list(self.response.response)
        buf.append(value)

    def writelines(self, seq):
        for item in seq:
            self.write(item)

    def close(self):
        self.closed = True

    def flush(self):
        if self.closed:
            raise ValueError('I/O operation on closed file')

    def isatty(self):
        if self.closed:
            raise ValueError('I/O operation on closed file')
        return False

    def encoding(self):
        return self.response.charset
    encoding = property(encoding)


class ResponseStreamMixin(object):
    """
    Mixin for `BaseRequest` subclasses.  Classes that inherit from this mixin
    will automatically get a `stream` property that provides a write-only
    interface to the response iterable.
    """

    def stream(self):
        """The response iterable as write-only stream."""
        return ResponseStream(self)
    stream = cached_property(stream)


class CommonResponseDescriptorsMixin(object):
    """
    A mixin for `BaseResponse` subclasses.  Response objects that mix this
    class in will automatically get descriptors for a couple of HTTP headers
    with automatic type conversion.
    """

    def _get_mimetype(self):
        """The mimetype (content type without charset etc.)"""
        ct = self.headers.get('Content-Type')
        if ct:
            return ct.split(';')[0].strip()

    def _set_mimetype(self, value):
        self.headers['Content-Type'] = get_content_type(value, self.charset)

    mimetype = property(_get_mimetype, _set_mimetype, doc='''
        The mimetype (content type without charset etc.)''')
    location = header_property('Location', doc='''
        The Location response-header field is used to redirect the recipient
        to a location other than the Request-URI for completion of the request
        or identification of a new resource.''')
    age = header_property('Age', None, parse_date, http_date, doc='''
        The Age response-header field conveys the sender's estimate of the
        amount of time since the response (or its revalidation) was
        generated at the origin server.

        Age values are non-negative decimal integers, representing time in
        seconds.''')
    content_type = header_property('Content-Type', doc='''
        The Content-Type entity-header field indicates the media type of the
        entity-body sent to the recipient or, in the case of the HEAD method,
        the media type that would have been sent had the request been a GET.
    ''')
    content_length = header_property('Content-Length', None, int, str, doc='''
        The Content-Length entity-header field indicates the size of the
        entity-body, in decimal number of OCTETs, sent to the recipient or,
        in the case of the HEAD method, the size of the entity-body that would
        have been sent had the request been a GET.''')
    content_location = header_property('Content-Location', doc='''
        The Content-Location entity-header field MAY be used to supply the
        resource location for the entity enclosed in the message when that
        entity is accessible from a location separate from the requested
        resource's URI.''')
    content_encoding = header_property('Content-Encoding', doc='''
        The Content-Encoding entity-header field is used as a modifier to the
        media-type.  When present, its value indicates what additional content
        codings have been applied to the entity-body, and thus what decoding
        mechanisms must be applied in order to obtain the media-type
        referenced by the Content-Type header field.''')
    content_md5 = header_property('Content-MD5', doc='''
         The Content-MD5 entity-header field, as defined in RFC 1864, is an
         MD5 digest of the entity-body for the purpose of providing an
         end-to-end message integrity check (MIC) of the entity-body.  (Note:
         a MIC is good for detecting accidental modification of the
         entity-body in transit, but is not proof against malicious attacks.)
        ''')
    date = header_property('Date', None, parse_date, http_date, doc='''
        The Date general-header field represents the date and time at which
        the message was originated, having the same semantics as orig-date
        in RFC 822.''')
    expires = header_property('Expires', None, parse_date, http_date, doc='''
        The Expires entity-header field gives the date/time after which the
        response is considered stale. A stale cache entry may not normally be
        returned by a cache.''')
    last_modified = header_property('Last-Modified', None, parse_date,
                                    http_date, doc='''
        The Last-Modified entity-header field indicates the date and time at
        which the origin server believes the variant was last modified.''')

    def _get_retry_after(self):
        value = self.headers.get('retry-after')
        if value is None:
            return
        elif value.isdigit():
            return datetime.utcnow() + timedelta(seconds=int(value))
        return parse_date(value)
    def _set_retry_after(self, value):
        if value is None:
            if 'retry-after' in self.headers:
                del self.headers['retry-after']
            return
        elif isinstance(value, datetime):
            value = http_date(value)
        else:
            value = str(value)
        self.headers['Retry-After'] = value

    retry_after = property(_get_retry_after, _set_retry_after, doc='''
        The Retry-After response-header field can be used with a 503 (Service
        Unavailable) response to indicate how long the service is expected
        to be unavailable to the requesting client.

        Time in seconds until expiration or date.''')

    def _set_property(name, doc=None):
        def fget(self):
            def on_update(header_set):
                if not header_set and name in self.headers:
                    del self.headers[name]
                elif header_set:
                    self.headers[name] = header_set.to_header()
            return parse_set_header(self.headers.get(name), on_update)
        return property(fget, doc)

    vary = _set_property('Vary', doc='''
         The Vary field value indicates the set of request-header fields that
         fully determines, while the response is fresh, whether a cache is
         permitted to use the response to reply to a subsequent request
         without revalidation.''')
    content_language = _set_property('Content-Language', doc='''
         The Content-Language entity-header field describes the natural
         language(s) of the intended audience for the enclosed entity.  Note
         that this might not be equivalent to all the languages used within
         the entity-body.''')
    allow = _set_property('Allow', doc='''
        The Allow entity-header field lists the set of methods supported
        by the resource identified by the Request-URI. The purpose of this
        field is strictly to inform the recipient of valid methods
        associated with the resource. An Allow header field MUST be
        present in a 405 (Method Not Allowed) response.''')

    del _set_property, _get_mimetype, _set_mimetype, _get_retry_after, \
        _set_retry_after


class Request(BaseRequest, AcceptMixin, ETagRequestMixin,
              UserAgentMixin):
    """
    Full featured request object implementing the following mixins:

    - `AcceptMixin` for accept header parsing
    - `ETagRequestMixin` for etag and cache control handling
    - `UserAgentMixin` for user agent introspection
    """


class Response(BaseResponse, ETagResponseMixin, ResponseStreamMixin,
               CommonResponseDescriptorsMixin):
    """
    Full featured response object implementing the following mixins:

    - `ETagResponseMixin` for etag and cache control handling
    - `ResponseStreamMixin` to add support for the `stream` property
    - `CommonResponseDescriptorsMixin` for various HTTP descriptors
    """


# XXX: backwards compatibility interface.  goes away with werkzeug 0.3
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
