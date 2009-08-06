# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    This module implements various utilities for WSGI applications.  Most of
    them are used by the request and response wrappers but especially for
    middleware development it makes sense to use them without the wrappers.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
import sys
import urllib
import urlparse
import posixpath
import mimetypes
from zlib import adler32
from time import time, mktime
from datetime import datetime, timedelta

from werkzeug._internal import _patch_wrapper, _decode_unicode, \
     _iter_modules, _ExtendedCookie, _ExtendedMorsel, \
     _DictAccessorProperty, _dump_date, _parse_signature, _missing


_format_re = re.compile(r'\$(?:(%s)|\{(%s)\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))
_entity_re = re.compile(r'&([^;]+);')
_filename_ascii_strip_re = re.compile(r'[^A-Za-z0-9_.-]')
_windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                         'LPT2', 'LPT3', 'PRN', 'NUL')


class SharedDataMiddleware(object):
    """A WSGI middleware that provides static content for development
    environments or simple server setups. Usage is quite simple::

        import os
        from werkzeug import SharedDataMiddleware

        app = SharedDataMiddleware(app, {
            '/shared': os.path.join(os.path.dirname(__file__), 'shared')
        })

    The contents of the folder ``./shared`` will now be available on
    ``http://example.com/shared/``.  This is pretty useful during development
    because a standalone media server is not required.  One can also mount
    files on the root folder and still continue to use the application because
    the shared data middleware forwards all unhandled requests to the
    application, even if the requests are below one of the shared folders.

    If `pkg_resources` is available you can also tell the middleware to serve
    files from package data::

        app = SharedDataMiddleware(app, {
            '/shared': ('myapplication', 'shared_files')
        })

    This will then serve the ``shared_files`` folder in the `myapplication`
    Python package.

    The optional `disallow` parameter can be a list of :func:`~fnmatch.fnmatch`
    rules for files that are not accessible from the web.  If `cache` is set to
    `False` no caching headers are sent.

    Currently the middleware does not support non ASCII filenames.  If the
    encoding on the file system happens to be the encoding of the URI it may
    work but this could also be by accident.  We strongly suggest using ASCII
    only file names for static files.

    .. versionchanged:: 0.5
       The cache timeout is configurable now.

    :param app: the application to wrap.  If you don't want to wrap an
                application you can pass it :exc:`NotFound`.
    :param exports: a dict of exported files and folders.
    :param diallow: a list of :func:`~fnmatch.fnmatch` rules.
    :param cache: enable or disable caching headers.
    :Param cache_timeout: the cache timeout in seconds for the headers.
    """

    def __init__(self, app, exports, disallow=None, cache=True,
                 cache_timeout=60 * 60 * 12):
        self.app = app
        self.exports = {}
        self.cache = cache
        self.cache_timeout = cache_timeout
        for key, value in exports.iteritems():
            if isinstance(value, tuple):
                loader = self.get_package_loader(*value)
            elif isinstance(value, basestring):
                if os.path.isfile(value):
                    loader = self.get_file_loader(value)
                else:
                    loader = self.get_directory_loader(value)
            else:
                raise TypeError('unknown def %r' % value)
            self.exports[key] = loader
        if disallow is not None:
            from fnmatch import fnmatch
            self.is_allowed = lambda x: not fnmatch(x, disallow)

    def is_allowed(self, filename):
        """Subclasses can override this method to disallow the access to
        certain files.  However by providing `disallow` in the constructor
        this method is overwritten.
        """
        return True

    def _opener(self, filename):
        return lambda: (
            open(filename, 'rb'),
            datetime.utcfromtimestamp(os.path.getmtime(filename)),
            int(os.path.getsize(filename))
        )

    def get_file_loader(self, filename):
        return lambda x: (os.path.basename(filename), self._opener(filename))

    def get_package_loader(self, package, package_path):
        from pkg_resources import DefaultProvider, ResourceManager, \
             get_provider
        loadtime = datetime.utcnow()
        provider = get_provider(package)
        manager = ResourceManager()
        filesystem_bound = isinstance(provider, DefaultProvider)
        def loader(path):
            path = posixpath.join(package_path, path)
            if path is None or not provider.has_resource(path):
                return None, None
            basename = posixpath.basename(path)
            if filesystem_bound:
                return basename, self._opener(
                    provider.get_resource_filename(manager, path))
            return basename, lambda: (
                provider.get_resource_stream(manager, path),
                loadtime,
                0
            )
        return loader

    def get_directory_loader(self, directory):
        def loader(path):
            if path is not None:
                path = os.path.join(directory, path)
            else:
                path = directory
            if os.path.isfile(path):
                return os.path.basename(path), self._opener(path)
            return None, None
        return loader

    def generate_etag(self, mtime, file_size, real_filename):
        return 'wzsdm-%d-%s-%s' % (
            mktime(mtime.timetuple()),
            file_size,
            adler32(real_filename) & 0xffffffff
        )

    def __call__(self, environ, start_response):
        # sanitize the path for non unix systems
        cleaned_path = environ.get('PATH_INFO', '').strip('/')
        for sep in os.sep, os.altsep:
            if sep and sep != '/':
                cleaned_path = cleaned_path.replace(sep, '/')
        path = '/'.join([''] + [x for x in cleaned_path.split('/')
                                if x and x != '..'])
        file_loader = None
        for search_path, loader in self.exports.iteritems():
            if search_path == path:
                real_filename, file_loader = loader(None)
                if file_loader is not None:
                    break
            if not search_path.endswith('/'):
                search_path += '/'
            if path.startswith(search_path):
                real_filename, file_loader = loader(path[len(search_path):])
                if file_loader is not None:
                    break
        if file_loader is None or not self.is_allowed(real_filename):
            return self.app(environ, start_response)

        guessed_type = mimetypes.guess_type(real_filename)
        mime_type = guessed_type[0] or 'text/plain'
        f, mtime, file_size = file_loader()

        headers = [('Date', http_date())]
        if self.cache:
            timeout = self.cache_timeout
            etag = self.generate_etag(mtime, file_size, real_filename)
            headers += [
                ('Etag', '"%s"' % etag),
                ('Cache-Control', 'max-age=%d, public' % timeout)
            ]
            if not is_resource_modified(environ, etag, last_modified=mtime):
                f.close()
                start_response('304 Not Modified', headers)
                return []
            headers.append(('Expires', http_date(time() + timeout)))
        else:
            headers.append(('Cache-Control', 'public'))

        headers.extend((
            ('Content-Type', mime_type),
            ('Content-Length', str(file_size)),
            ('Last-Modified', http_date(mtime))
        ))
        start_response('200 OK', headers)
        return wrap_file(environ, f)


class DispatcherMiddleware(object):
    """Allows one to mount middlewares or application in a WSGI application.
    This is useful if you want to combine multiple WSGI applications::

        app = DispatcherMiddleware(app, {
            '/app2':        app2,
            '/app3':        app3
        })
    """

    def __init__(self, app, mounts=None):
        self.app = app
        self.mounts = mounts or {}

    def __call__(self, environ, start_response):
        script = environ.get('PATH_INFO', '')
        path_info = ''
        while '/' in script:
            if script in self.mounts:
                app = self.mounts[script]
                break
            items = script.split('/')
            script = '/'.join(items[:-1])
            path_info = '/%s%s' % (items[-1], path_info)
        else:
            app = self.mounts.get(script, self.app)
        original_script_name = environ.get('SCRIPT_NAME', '')
        environ['SCRIPT_NAME'] = original_script_name + script
        environ['PATH_INFO'] = path_info
        return app(environ, start_response)


class ClosingIterator(object):
    """The WSGI specification requires that all middlewares and gateways
    respect the `close` callback of an iterator.  Because it is useful to add
    another close action to a returned iterator and adding a custom iterator
    is a boring task this class can be used for that::

        return ClosingIterator(app(environ, start_response), [cleanup_session,
                                                              cleanup_locals])

    If there is just one close function it can be passed instead of the list.

    A closing iterator is not needed if the application uses response objects
    and finishes the processing if the response is started::

        try:
            return response(environ, start_response)
        finally:
            cleanup_session()
            cleanup_locals()
    """

    def __init__(self, iterable, callbacks=None):
        iterator = iter(iterable)
        self._next = iterator.next
        if callbacks is None:
            callbacks = []
        elif callable(callbacks):
            callbacks = [callbacks]
        else:
            callbacks = list(callbacks)
        iterable_close = getattr(iterator, 'close', None)
        if iterable_close:
            callbacks.insert(0, iterable_close)
        self._callbacks = callbacks

    def __iter__(self):
        return self

    def next(self):
        return self._next()

    def close(self):
        for callback in self._callbacks:
            callback()


class FileWrapper(object):
    """This class can be used to convert a :class:`file`-like object into
    an iterable.  It yields `buffer_size` blocks until the file is fully
    read.

    You should not use this class directly but rather use the
    :func:`wrap_file` function that uses the WSGI server's file wrapper
    support if it's available.

    .. versionadded:: 0.5

    :param file: a :class:`file`-like object with a :meth:`~file.read` method.
    :param buffer_size: number of bytes for one iteration.
    """

    def __init__(self, file, buffer_size=8192):
        self.file = file
        self.buffer_size = buffer_size

    def close(self):
        if hasattr(self.file, 'close'):
            self.file.close()

    def __iter__(self):
        return self

    def next(self):
        data = self.file.read(self.buffer_size)
        if data:
            return data
        raise StopIteration()



def make_line_iter(stream, limit=None, buffer_size=10 * 1024):
    """Savely iterates line-based over an input stream.  If the input stream
    is not a :class:`LimitedStream` the `limit` parameter is mandatory.

    This uses the stream's :meth:`~file.read` method internally as opposite
    to the :meth:`~file.readline` method that is unsafe and can only be used
    in violation of the WSGI specification.  The same problem applies to the
    `__iter__` function of the input stream which calls :meth:`~file.readline`
    without arguments.

    If you need line-by-line processing it's strongly recommended to iterate
    over the input stream using this helper function.

    :param stream: the stream to iterate over.
    :param limit: the limit in bytes for the stream.  (Usually
                  content length.  Not necessary if the `stream`
                  is a :class:`LimitedStream`.
    :param buffer_size: The optional buffer size.
    """
    if not isinstance(stream, LimitedStream):
        if limit is None:
            raise TypeError('stream not limited and no limit provided.')
        stream = LimitedStream(stream, limit)
    _read = stream.read
    buffer = []
    while 1:
        if len(buffer) > 1:
            yield buffer.pop(0)
            continue
        chunks = _read(buffer_size).splitlines(True)
        first_chunk = buffer and buffer[0] or ''
        if chunks:
            first_chunk += chunks.pop(0)
        buffer = chunks
        if not first_chunk:
            return
        yield first_chunk


class LimitedStream(object):
    """Wraps a stream so that it doesn't read more than n bytes.  If the
    stream is exhausted and the caller tries to get more bytes from it
    :func:`on_exhausted` is called which by default returns an empty
    string or raises :exc:`~werkzeug.exceptions.BadRequest` if silent
    is set to `False`.  The return value of that function is forwarded
    to the reader function.  So if it returns an empty string
    :meth:`read` will return an empty string as well.

    The limit however must never be higher than what the stream can
    output.  Otherwise :meth:`readlines` will try to read past the
    limit.

    The `silent` parameter has no effect if :meth:`is_exhausted` is
    overriden by a subclass.

    .. admonition:: Note on WSGI compliance

       calls to :meth:`readline` and :meth:`readlines` are not
       WSGI compliant because it passes a size argument to the
       readline methods.  Unfortunately the WSGI PEP is not safely
       implementable without a size argument to :meth:`readline`
       because there is no EOF marker in the stream.  As a result
       of that the use of :meth:`readline` is discouraged.

       For the same reason iterating over the :class:`LimitedStream`
       is not portable.  It internally calls :meth:`readline`.

       We strongly suggest using :meth:`read` only or using the
       :func:`make_line_iter` which savely iterates line-based
       over a WSGI input stream.

    :param stream: the stream to wrap.
    :param limit: the limit for the stream, must not be longer than
                  what the string can provide if the stream does not
                  end with `EOF` (like `wsgi.input`)
    :param silent: If set to `True` the stream will allow reading
                   past the limit and will return an empty string.
    """

    def __init__(self, stream, limit, silent=True):
        self._stream = stream
        self._pos = 0
        self.limit = limit
        self.silent = silent

    def __iter__(self):
        return self

    @property
    def is_exhausted(self):
        """If the stream is exhausted this attribute is `True`."""
        return self._pos >= self.limit

    def on_exhausted(self):
        """This is called when the stream tries to read past the limit.
        The return value of this function is returned from the reading
        function.

        Per default this raises a :exc:`~werkzeug.exceptions.BadRequest`.
        """
        if self.silent:
            return ''
        raise BadRequest('input stream exhausted')

    def exhaust(self, chunk_size=1024 * 16):
        """Exhaust the stream.  This consumes all the data left until the
        limit is reached.

        :param chunk_size: the size for a chunk.  It will read the chunk
                           until the stream is exhausted and throw away
                           the results.
        """
        to_read = self.limit - self._pos
        chunk = chunk_size
        while to_read > 0:
            chunk = min(to_read, chunk)
            self.read(chunk)
            to_read -= chunk

    def read(self, size=None):
        """Read `size` bytes or if size is not provided everything is read.

        :param size: the number of bytes read.
        """
        if self._pos >= self.limit:
            return self.on_exhausted()
        if size is None:
            size = self.limit
        read = self._stream.read(min(self.limit - self._pos, size))
        self._pos += len(read)
        return read

    def readline(self, size=None):
        """Reads one line from the stream."""
        if self._pos >= self.limit:
            return self.on_exhausted()
        if size is None:
            size = self.limit - self._pos
        else:
            size = min(size, self.limit - self._pos)
        line = self._stream.readline(size)
        self._pos += len(line)
        return line

    def readlines(self, size=None):
        """Reads a file into a list of strings.  It calls :meth:`readline`
        until the file is read to the end.  It does support the optional
        `size` argument if the underlaying stream supports it for
        `readline`.
        """
        last_pos = self._pos
        result = []
        if size is not None:
            end = min(self.limit, last_pos + size)
        else:
            end = self.limit
        while 1:
            if size is not None:
                size -= last_pos - self._pos
            if self._pos >= end:
                break
            result.append(self.readline(size))
            if size is not None:
                last_pos = self._pos
        return result

    def next(self):
        line = self.readline()
        if line is None:
            raise StopIteration()
        return line


class cached_property(object):
    """A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and than that calculated result is used the next time you access
    the value::

        class Foo(object):

            @cached_property
            def foo(self):
                # calculate something important here
                return 42

    The class has to have a `__dict__` in order for this property to
    work.

    .. versionchanged:: 0.6
       the `writeable` attribute and parameter was deprecated.  If a
       cached property is writeable or not has to be documented now.
       For performance reasons the implementation does not honor the
       writeable setting and will always make the property writeable.
    """

    # implementation detail: this property is implemented as non-data
    # descriptor.  non-data descriptors are only invoked if there is
    # no entry with the same name in the instance's __dict__
    # this allows us to completely get rid of the access function call
    # overhead.  If one choses to invoke __get__ by hand the property
    # will still work as expected because the lookup logic is replicated
    # in __get__ for manual invocation.

    def __init__(self, func, name=None, doc=None, writeable=False):
        if writeable:
            from warnings import warn
            warn(DeprecationWarning('the writeable argument to the '
                                    'cached property is a noop since 0.6 '
                                    'because the property is writeable '
                                    'by default for performance reasons'))

        self.__name__ = name or func.__name__
        self.__doc__ = doc
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


class environ_property(_DictAccessorProperty):
    """Maps request attributes to environment variables. This works not only
    for the Werzeug request object, but also any other class with an
    environ attribute:

    >>> class Test(object):
    ...     environ = {'key': 'value'}
    ...     test = environ_property('key')
    >>> var = Test()
    >>> var.test
    'value'

    If you pass it a second value it's used as default if the key does not
    exist, the third one can be a converter that takes a value and converts
    it.  If it raises :exc:`ValueError` or :exc:`TypeError` the default value
    is used. If no default value is provided `None` is used.

    Per default the property is read only.  You have to explicitly enable it
    by passing ``read_only=False`` to the constructor.
    """

    read_only = True

    def lookup(self, obj):
        return obj.environ


class header_property(_DictAccessorProperty):
    """Like `environ_property` but for headers."""

    def lookup(self, obj):
        return obj.headers


class HTMLBuilder(object):
    """Helper object for HTML generation.

    Per default there are two instances of that class.  The `html` one, and
    the `xhtml` one for those two dialects.  The class uses keyword parameters
    and positional parameters to generate small snippets of HTML.

    Keyword parameters are converted to XML/SGML attributes, positional
    arguments are used as children.  Because Python accepts positional
    arguments before keyword arguments it's a good idea to use a list with the
    star-syntax for some children:

    >>> html.p(class_='foo', *[html.a('foo', href='foo.html'), ' ',
    ...                        html.a('bar', href='bar.html')])
    u'<p class="foo"><a href="foo.html">foo</a> <a href="bar.html">bar</a></p>'

    This class works around some browser limitations and can not be used for
    arbitrary SGML/XML generation.  For that purpose lxml and similar
    libraries exist.

    Calling the builder escapes the string passed:

    >>> html.p(html("<foo>"))
    u'<p>&lt;foo&gt;</p>'
    """

    from htmlentitydefs import name2codepoint
    _entity_re = re.compile(r'&([^;]+);')
    _entities = name2codepoint.copy()
    _entities['apos'] = 39
    _empty_elements = set([
        'area', 'base', 'basefont', 'br', 'col', 'frame', 'hr', 'img',
        'input', 'isindex', 'link', 'meta', 'param'
    ])
    _boolean_attributes = set([
        'selected', 'checked', 'compact', 'declare', 'defer', 'disabled',
        'ismap', 'multiple', 'nohref', 'noresize', 'noshade', 'nowrap'
    ])
    _plaintext_elements = set(['textarea'])
    _c_like_cdata = set(['script', 'style'])
    del name2codepoint

    def __init__(self, dialect):
        self._dialect = dialect

    def __call__(self, s):
        return escape(s)

    def __getattr__(self, tag):
        if tag[:2] == '__':
            raise AttributeError(tag)
        def proxy(*children, **arguments):
            buffer = ['<' + tag]
            write = buffer.append
            for key, value in arguments.iteritems():
                if value is None:
                    continue
                if key.endswith('_'):
                    key = key[:-1]
                if key in self._boolean_attributes:
                    if not value:
                        continue
                    value = self._dialect == 'xhtml' and '="%s"' % key or ''
                else:
                    value = '="%s"' % escape(value, True)
                write(' ' + key + value)
            if not children and tag in self._empty_elements:
                write(self._dialect == 'xhtml' and ' />' or '>')
                return ''.join(buffer)
            write('>')
            children_as_string = ''.join(unicode(x) for x in children
                                         if x is not None)
            if children_as_string:
                if tag in self._plaintext_elements:
                    children_as_string = escape(children_as_string)
                elif tag in self._c_like_cdata and self._dialect == 'xhtml':
                    children_as_string = '/*<![CDATA[*/%s/*]]>*/' % \
                                         children_as_string
            buffer.extend((children_as_string, '</%s>' % tag))
            return ''.join(buffer)
        return proxy

    def __repr__(self):
        return '<%s for %r>' % (
            self.__class__.__name__,
            self._dialect
        )


html = HTMLBuilder('html')
xhtml = HTMLBuilder('xhtml')


def get_current_url(environ, root_only=False, strip_querystring=False,
                    host_only=False):
    """A handy helper function that recreates the full URL for the current
    request or parts of it.  Here an example:

    >>> from werkzeug import create_environ
    >>> env = create_environ("/?param=foo", "http://localhost/script")
    >>> get_current_url(env)
    'http://localhost/script/?param=foo'
    >>> get_current_url(env, root_only=True)
    'http://localhost/script/'
    >>> get_current_url(env, host_only=True)
    'http://localhost/'
    >>> get_current_url(env, strip_querystring=True)
    'http://localhost/script/'

    :param environ: the WSGI environment to get the current URL from.
    :param root_only: set `True` if you only want the root URL.
    :param strip_querystring: set to `True` if you don't want the querystring.
    :param host_only: set to `True` if the host URL should be returned.
    """
    tmp = [environ['wsgi.url_scheme'], '://', get_host(environ)]
    cat = tmp.append
    if host_only:
        return ''.join(tmp) + '/'
    cat(urllib.quote(environ.get('SCRIPT_NAME', '').rstrip('/')))
    if root_only:
        cat('/')
    else:
        cat(urllib.quote('/' + environ.get('PATH_INFO', '').lstrip('/')))
        if not strip_querystring:
            qs = environ.get('QUERY_STRING')
            if qs:
                cat('?' + qs)
    return ''.join(tmp)


def get_content_type(mimetype, charset):
    """Return the full content type string with charset for a mimetype.

    If the mimetype represents text the charset will be appended as charset
    parameter, otherwise the mimetype is returned unchanged.

    :param mimetype: the mimetype to be used as content type.
    :param charset: the charset to be appended in case it was a text mimetype.
    :return: the content type.
    """
    if mimetype.startswith('text/') or \
       mimetype == 'application/xml' or \
       (mimetype.startswith('application/') and
        mimetype.endswith('+xml')):
        mimetype += '; charset=' + charset
    return mimetype


def format_string(string, context):
    """String-template format a string:

    >>> format_string('$foo and ${foo}s', dict(foo=42))
    '42 and 42s'

    This does not do any attribute lookup etc.  For more advanced string
    formattings have a look at the `werkzeug.template` module.

    :param string: the format string.
    :param context: a dict with the variables to insert.
    """
    def lookup_arg(match):
        x = context[match.group(1) or match.group(2)]
        if not isinstance(x, basestring):
            x = type(string)(x)
        return x
    return _format_re.sub(lookup_arg, string)


def secure_filename(filename):
    r"""Pass it a filename and it will return a secure version of it.  This
    filename can then savely be stored on a regular file system and passed
    to :func:`os.path.join`.  The filename returned is an ASCII only string
    for maximum portability.

    On windows system the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename(u'i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename.  It's your responsibility
    to ensure that the filename is unique and that you generate random
    filename if the function returned an empty one.

    .. versionadded:: 0.5

    :param filename: the filename to secure
    """
    if isinstance(filename, unicode):
        from unicodedata import normalize
        filename = normalize('NFKD', filename).encode('ascii', 'ignore')
    for sep in os.path.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, ' ')
    filename = str(_filename_ascii_strip_re.sub('', '_'.join(
                   filename.split()))).strip('._')

    # on nt a couple of special files are present in each folder.  We
    # have to ensure that the target file is not such a filename.  In
    # this case we prepend an underline
    if os.name == 'nt' and filename and \
       filename.split('.')[0].upper() in _windows_device_files:
        filename = '_' + filename

    return filename


def escape(s, quote=False):
    """Replace special characters "&", "<" and ">" to HTML-safe sequences.  If
    the optional flag `quote` is `True`, the quotation mark character (") is
    also translated.

    There is a special handling for `None` which escapes to an empty string.

    :param s: the string to escape.
    :param quote: set to true to also escape double quotes.
    """
    if s is None:
        return ''
    elif hasattr(s, '__html__'):
        return s.__html__()
    elif not isinstance(s, basestring):
        s = unicode(s)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if quote:
        s = s.replace('"', "&quot;")
    return s


def unescape(s):
    """The reverse function of `escape`.  This unescapes all the HTML
    entities, not only the XML entities inserted by `escape`.

    :param s: the string to unescape.
    """
    def handle_match(m):
        name = m.group(1)
        if name in HTMLBuilder._entities:
            return unichr(HTMLBuilder._entities[name])
        try:
            if name[:2] in ('#x', '#X'):
                return unichr(int(name[2:], 16))
            elif name.startswith('#'):
                return unichr(int(name[1:]))
        except ValueError:
            pass
        return u''
    return _entity_re.sub(handle_match, s)


def get_host(environ):
    """Return the real host for the given WSGI environment.  This takes care
    of the `X-Forwarded-Host` header.

    :param environ: the WSGI environment to get the host of.
    """
    if 'HTTP_X_FORWARDED_HOST' in environ:
        return environ['HTTP_X_FORWARDED_HOST']
    elif 'HTTP_HOST' in environ:
        return environ['HTTP_HOST']
    result = environ['SERVER_NAME']
    if (environ['wsgi.url_scheme'], environ['SERVER_PORT']) not \
       in (('https', '443'), ('http', '80')):
        result += ':' + environ['SERVER_PORT']
    return result


def pop_path_info(environ):
    """Removes and returns the next segment of `PATH_INFO`, pushing it onto
    `SCRIPT_NAME`.  Returns `None` if there is nothing left on `PATH_INFO`.

    If there are empty segments (``'/foo//bar``) these are ignored but
    properly pushed to the `SCRIPT_NAME`:

    >>> env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b'}
    >>> pop_path_info(env)
    'a'
    >>> env['SCRIPT_NAME']
    '/foo/a'
    >>> pop_path_info(env)
    'b'
    >>> env['SCRIPT_NAME']
    '/foo/a/b'

    .. versionadded:: 0.5

    :param environ: the WSGI environment that is modified.
    """
    path = environ.get('PATH_INFO')
    if not path:
        return None

    script_name = environ.get('SCRIPT_NAME', '')

    # shift multiple leading slashes over
    old_path = path
    path = path.lstrip('/')
    if path != old_path:
        script_name += '/' * (len(old_path) - len(path))

    if '/' not in path:
        environ['PATH_INFO'] = ''
        environ['SCRIPT_NAME'] = script_name + path
        return path

    segment, path = path.split('/', 1)
    environ['PATH_INFO'] = '/' + path
    environ['SCRIPT_NAME'] = script_name + segment
    return segment


def peek_path_info(environ):
    """Returns the next segment on the `PATH_INFO` or `None` if there
    is none.  Works like :func:`pop_path_info` without modifying the
    environment:

    >>> env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b'}
    >>> peek_path_info(env)
    'a'
    >>> peek_path_info(env)
    'a'

    .. versionadded:: 0.5

    :param environ: the WSGI environment that is checked.
    """
    segments = environ.get('PATH_INFO', '').lstrip('/').split('/', 1)
    if segments:
        return segments[0]


def cookie_date(expires=None):
    """Formats the time to ensure compatibility with Netscape's cookie
    standard.

    Accepts a floating point number expressed in seconds since the epoc in, a
    datetime object or a timetuple.  All times in UTC.  The :func:`parse_date`
    function can be used to parse such a date.

    Outputs a string in the format ``Wdy, DD-Mon-YYYY HH:MM:SS GMT``.

    :param expires: If provided that date is used, otherwise the current.
    """
    return _dump_date(expires, '-')


def parse_cookie(header, charset='utf-8', errors='ignore',
                 cls=None):
    """Parse a cookie.  Either from a string or WSGI environ.

    Per default encoding errors are ignored.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    :exc:`HTTPUnicodeError` is raised.

    .. versionchanged:: 0.5
       This function now returns a :class:`TypeConversionDict` instead of a
       regular dict.  The `cls` parameter was added.

    :param header: the header to be used to parse the cookie.  Alternatively
                   this can be a WSGI environment.
    :param charset: the charset for the cookie values.
    :param errors: the error behavior for the charset decoding.
    :param cls: an optional dict class to use.  If this is not specified
                       or `None` the default :class:`TypeConversionDict` is
                       used.
    """
    if isinstance(header, dict):
        header = header.get('HTTP_COOKIE', '')
    if cls is None:
        cls = TypeConversionDict
    cookie = _ExtendedCookie()
    cookie.load(header)
    result = {}

    # decode to unicode and skip broken items.  Our extended morsel
    # and extended cookie will catch CookieErrors and convert them to
    # `None` items which we have to skip here.
    for key, value in cookie.iteritems():
        if value.value is not None:
            result[key] = _decode_unicode(unquote_header_value(value.value),
                                          charset, errors)

    return cls(result)


def dump_cookie(key, value='', max_age=None, expires=None, path='/',
                domain=None, secure=None, httponly=False, charset='utf-8',
                sync_expires=True):
    """Creates a new Set-Cookie header without the ``Set-Cookie`` prefix
    The parameters are the same as in the cookie Morsel object in the
    Python standard library but it accepts unicode data, too.

    :param max_age: should be a number of seconds, or `None` (default) if
                    the cookie should last only as long as the client's
                    browser session.  Additionally `timedelta` objects
                    are accepted, too.
    :param expires: should be a `datetime` object or unix timestamp.
    :param path: limits the cookie to a given path, per default it will
                 span the whole domain.
    :param domain: Use this if you want to set a cross-domain cookie. For
                   example, ``domain=".example.com"`` will set a cookie
                   that is readable by the domain ``www.example.com``,
                   ``foo.example.com`` etc. Otherwise, a cookie will only
                   be readable by the domain that set it.
    :param secure: The cookie will only be available via HTTPS
    :param httponly: disallow JavaScript to access the cookie.  This is an
                     extension to the cookie standard and probably not
                     supported by all browsers.
    :param charset: the encoding for unicode values.
    :param sync_expires: automatically set expires if max_age is defined
                         but expires not.
    """
    try:
        key = str(key)
    except UnicodeError:
        raise TypeError('invalid key %r' % key)
    if isinstance(value, unicode):
        value = value.encode(charset)
    value = quote_header_value(value)
    morsel = _ExtendedMorsel(key, value)
    if isinstance(max_age, timedelta):
        max_age = (max_age.days * 60 * 60 * 24) + max_age.seconds
    if expires is not None:
        if not isinstance(expires, basestring):
            expires = cookie_date(expires)
        morsel['expires'] = expires
    elif max_age is not None and sync_expires:
        morsel['expires'] = cookie_date(time() + max_age)
    for k, v in (('path', path), ('domain', domain), ('secure', secure),
                 ('max-age', max_age), ('httponly', httponly)):
        if v is not None and v is not False:
            morsel[k] = str(v)
    return morsel.output(header='').lstrip()


def http_date(timestamp=None):
    """Formats the time to match the RFC1123 date format.

    Accepts a floating point number expressed in seconds since the epoc in, a
    datetime object or a timetuple.  All times in UTC.  The :func:`parse_date`
    function can be used to parse such a date.

    Outputs a string in the format ``Wdy, DD Mon YYYY HH:MM:SS GMT``.

    :param timestamp: If provided that date is used, otherwise the current.
    """
    return _dump_date(timestamp, ' ')


def redirect(location, code=302):
    """Return a response object (a WSGI application) that, if called,
    redirects the client to the target location.  Supported codes are 301,
    302, 303, 305, and 307.  300 is not supported because it's not a real
    redirect and 304 because it's the answer for a request with a request
    with defined If-Modified-Since headers.

    :param location: the location the response should redirect to.
    :param code: the redirect status code.
    """
    assert code in (301, 302, 303, 305, 307), 'invalid code'
    from werkzeug.wrappers import BaseResponse
    response = BaseResponse(
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
        '<title>Redirecting...</title>\n'
        '<h1>Redirecting...</h1>\n'
        '<p>You should be redirected automatically to target URL: '
        '<a href="%s">%s</a>.  If not click the link.' %
        ((escape(location),) * 2), code, mimetype='text/html')
    response.headers['Location'] = location
    return response


def append_slash_redirect(environ, code=301):
    """Redirect to the same URL but with a slash appended.  The behavior
    of this function is undefined if the path ends with a slash already.

    :param environ: the WSGI environment for the request that triggers
                    the redirect.
    :param code: the status code for the redirect.
    """
    new_path = environ['PATH_INFO'].strip('/') + '/'
    query_string = environ.get('QUERY_STRING')
    if query_string:
        new_path += '?' + query_string
    return redirect(new_path, code)


def responder(f):
    """Marks a function as responder.  Decorate a function with it and it
    will automatically call the return value as WSGI application.

    Example::

        @responder
        def application(environ, start_response):
            return Response('Hello World!')
    """
    return _patch_wrapper(f, lambda *a: f(*a)(*a[-2:]))


def wrap_file(environ, file, buffer_size=8192):
    """Wraps a file.  This uses the WSGI server's file wrapper if available
    or otherwise the generic :class:`FileWrapper`.

    .. versionadded:: 0.5

    If the file wrapper from the WSGI server is used it's important to not
    iterate over it from inside the application but to pass it through
    unchanged.  If you want to pass out a file wrapper inside a response
    object you have to set :attr:`~BaseResponse.direct_passthrough` to `True`.

    More information about file wrappers are available in :pep:`333`.

    :param file: a :class:`file`-like object with a :meth:`~file.read` method.
    :param buffer_size: number of bytes for one iteration.
    """
    return environ.get('wsgi.file_wrapper', FileWrapper)(file, buffer_size)


def import_string(import_name, silent=False):
    """Imports an object based on a string.  This is useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).

    If `silent` is True the return value will be `None` if the import fails.

    :param import_name: the dotted name for the object to import.
    :param silent: if set to `True` import errors are ignored and
                   `None` is returned instead.
    :return: imported object
    """
    try:
        if ':' in import_name:
            module, obj = import_name.split(':', 1)
        elif '.' in import_name:
            module, obj = import_name.rsplit('.', 1)
        else:
            return __import__(import_name)
        return getattr(__import__(module, None, None, [obj]), obj)
    except (ImportError, AttributeError):
        if not silent:
            raise


def find_modules(import_path, include_packages=False, recursive=False):
    """Find all the modules below a package.  This can be useful to
    automatically import all views / controllers so that their metaclasses /
    function decorators have a chance to register themselves on the
    application.

    Packages are not returned unless `include_packages` is `True`.  This can
    also recursively list modules but in that case it will import all the
    packages to get the correct load path of that module.

    :param import_name: the dotted name for the package to find child modules.
    :param include_packages: set to `True` if packages should be returned, too.
    :param recursive: set to `True` if recursion should happen.
    :return: generator
    """
    module = import_string(import_path)
    path = getattr(module, '__path__', None)
    if path is None:
        raise ValueError('%r is not a package' % import_path)
    basename = module.__name__ + '.'
    for modname, ispkg in _iter_modules(path):
        modname = basename + modname
        if ispkg:
            if include_packages:
                yield modname
            if recursive:
                for item in find_modules(modname, include_packages, True):
                    yield item
        else:
            yield modname


def validate_arguments(func, args, kwargs, drop_extra=True):
    """Check if the function accepts the arguments and keyword arguments.
    Returns a new ``(args, kwargs)`` tuple that can savely be passed to
    the function without causing a `TypeError` because the function signature
    is incompatible.  If `drop_extra` is set to `True` (which is the default)
    any extra positional or keyword arguments are dropped automatically.

    The exception raised provides three attributes:

    `missing`
        A set of argument names that the function expected but where
        missing.

    `extra`
        A dict of keyword arguments that the function can not handle but
        where provided.

    `extra_positional`
        A list of values that where given by positional argument but the
        function cannot accept.

    This can be useful for decorators that forward user submitted data to
    a view function::

        from werkzeug import ArgumentValidationError, validate_arguments

        def sanitize(f):
            def proxy(request):
                data = request.values.to_dict()
                try:
                    args, kwargs = validate_arguments(f, (request,), data)
                except ArgumentValidationError:
                    raise BadRequest('The browser failed to transmit all '
                                     'the data expected.')
                return f(*args, **kwargs)
            return proxy

    :param func: the function the validation is performed against.
    :param args: a tuple of positional arguments.
    :param kwargs: a dict of keyword arguments.
    :param drop_extra: set to `False` if you don't want extra arguments
                       to be silently dropped.
    :return: tuple in the form ``(args, kwargs)``.
    """
    parser = _parse_signature(func)
    args, kwargs, missing, extra, extra_positional = parser(args, kwargs)[:5]
    if missing:
        raise ArgumentValidationError(tuple(missing))
    elif (extra or extra_positional) and not drop_extra:
        raise ArgumentValidationError(None, extra, extra_positional)
    return tuple(args), kwargs


def bind_arguments(func, args, kwargs):
    """Bind the arguments provided into a dict.  When passed a function,
    a tuple of arguments and a dict of keyword arguments `bind_arguments`
    returns a dict of names as the function would see it.  This can be useful
    to implement a cache decorator that uses the function arguments to build
    the cache key based on the values of the arguments.

    :param func: the function the arguments should be bound for.
    :param args: tuple of positional arguments.
    :param kwargs: a dict of keyword arguments.
    :return: a :class:`dict` of bound keyword arguments.
    """
    args, kwargs, missing, extra, extra_positional, \
        arg_spec, vararg_var, kwarg_var = _parse_signature(func)(args, kwargs)
    values = {}
    for (name, has_default, default), value in zip(arg_spec, args):
        values[name] = value
    if vararg_var is not None:
        values[vararg_var] = tuple(extra_positional)
    elif extra_positional:
        raise TypeError('too many positional arguments')
    if kwarg_var is not None:
        multikw = set(extra) & set([x[0] for x in arg_spec])
        if multikw:
            raise TypeError('got multiple values for keyword argument ' +
                            repr(iter(multikw).next()))
        values[kwarg_var] = extra
    elif extra:
        raise TypeError('got unexpected keyword argument ' +
                        repr(iter(extra).next()))
    return values


class ArgumentValidationError(ValueError):
    """Raised if :func:`validate_arguments` fails to validate"""

    def __init__(self, missing=None, extra=None, extra_positional=None):
        self.missing = set(missing or ())
        self.extra = extra or {}
        self.extra_positional = extra_positional or []
        ValueError.__init__(self, 'function arguments invalid.  ('
                            '%d missing, %d additional)' % (
            len(self.missing),
            len(self.extra) + len(self.extra_positional)
        ))


# circular dependency fun
from werkzeug.http import is_resource_modified, quote_header_value, \
     unquote_header_value
from werkzeug.exceptions import BadRequest
from werkzeug.datastructures import TypeConversionDict


# DEPRECATED
# these objects were previously in this module as well.  we import
# them here for backwards compatibility with old pickles.
from werkzeug.datastructures import MultiDict, CombinedMultiDict, \
     Headers, EnvironHeaders
