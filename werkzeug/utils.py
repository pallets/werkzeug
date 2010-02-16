# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    This module implements various utilities for WSGI applications.  Most of
    them are used by the request and response wrappers but especially for
    middleware development it makes sense to use them without the wrappers.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
from time import time
from datetime import datetime, timedelta

from werkzeug._internal import _decode_unicode, \
     _iter_modules, _ExtendedCookie, _ExtendedMorsel, \
     _DictAccessorProperty, _dump_date, _parse_signature, _missing


_format_re = re.compile(r'\$(?:(%s)|\{(%s)\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))
_entity_re = re.compile(r'&([^;]+);')
_filename_ascii_strip_re = re.compile(r'[^A-Za-z0-9_.-]')
_windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                         'LPT2', 'LPT3', 'PRN', 'NUL')


class cached_property(object):
    """A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
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
    # no entry with the same name in the instance's __dict__.
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
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
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
    filename can then safely be stored on a regular file system and passed
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


def cookie_date(expires=None):
    """Formats the time to ensure compatibility with Netscape's cookie
    standard.

    Accepts a floating point number expressed in seconds since the epoch in, a
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

    Accepts a floating point number expressed in seconds since the epoch in, a
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

    .. versionadded:: 0.6
       The location can now be a unicode string that is encoded using
       the :func:`iri_to_uri` function.

    :param location: the location the response should redirect to.
    :param code: the redirect status code.
    """
    assert code in (301, 302, 303, 305, 307), 'invalid code'
    from werkzeug.wrappers import BaseResponse
    display_location = location
    if isinstance(location, unicode):
        from werkzeug.urls import iri_to_uri
        location = iri_to_uri(location)
    response = BaseResponse(
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
        '<title>Redirecting...</title>\n'
        '<h1>Redirecting...</h1>\n'
        '<p>You should be redirected automatically to target URL: '
        '<a href="%s">%s</a>.  If not click the link.' %
        (location, display_location), code, mimetype='text/html')
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
    # force the import name to automatically convert to strings
    if isinstance(import_name, unicode):
        import_name = str(import_name)
    try:
        if ':' in import_name:
            module, obj = import_name.split(':', 1)
        elif '.' in import_name:
            module, obj = import_name.rsplit('.', 1)
        else:
            return __import__(import_name)
        # __import__ is not able to handle unicode strings in the fromlist
        # if the module is a package
        if isinstance(obj, unicode):
            obj = obj.encode('utf-8')
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
    Returns a new ``(args, kwargs)`` tuple that can safely be passed to
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


# circular dependencies
from werkzeug.http import quote_header_value, unquote_header_value
from werkzeug.exceptions import BadRequest
from werkzeug.datastructures import TypeConversionDict


# DEPRECATED
# these objects were previously in this module as well.  we import
# them here for backwards compatibility with old pickles.
from werkzeug.datastructures import MultiDict, CombinedMultiDict, \
     Headers, EnvironHeaders
