# -*- coding: utf-8 -*-
"""
    werkzeug.urls
    ~~~~~~~~~~~~~

    This module implements various URL related functions.

    :copyright: (c) 2011 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import six

from werkzeug._compat import urlparse, to_bytes, to_native

from werkzeug._internal import _decode_unicode
from werkzeug.datastructures import MultiDict, iter_multi_items
from werkzeug.wsgi import make_chunk_iter


from werkzeug._urlparse import (
    quote as _quote, quote_plus as url_quote_plus,
    unquote as url_unquote, unquote_plus as url_unquote_plus,
    urlsplit as _safe_urlsplit,
)


def url_quote(string, encoding=None, safe='/:', errors=None):
    # we also consider : safe since it's commonly used
    return _quote(string, safe=safe, encoding=encoding, errors=errors)


def _uri_split(uri):
    """Splits up an URI or IRI."""
    uri, coerce_rv = urlparse._coerce_args(uri)
    scheme, netloc, path, query, fragment = _safe_urlsplit(uri)

    port = None

    if u'@' in netloc:
        auth, hostname = netloc.split(u'@', 1)
    else:
        auth = None
        hostname = netloc
    if hostname:
        if u':' in hostname:
            hostname, port = hostname.split(u':', 1)

    rv = scheme, auth, hostname, port, path, query, fragment
    return tuple(x if x is None else coerce_rv(x) for x in rv)


def iri_to_uri(iri, charset='utf-8'):
    r"""Converts any unicode based IRI to an acceptable ASCII URI.  Werkzeug
    always uses utf-8 URLs internally because this is what browsers and HTTP
    do as well.  In some places where it accepts an URL it also accepts a
    unicode IRI and converts it into a URI.

    Examples for IRI versus URI:

    >>> iri_to_uri(u'http://☃.net/')
    b'http://xn--n3h.net/'
    >>> iri_to_uri(u'http://üser:pässword@☃.net/påth')
    b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'

    .. versionadded:: 0.6

    :param iri: the iri to convert
    :param charset: the charset for the URI
    """
    if isinstance(iri, bytes):
        iri = iri.decode(charset)
    scheme, auth, hostname, port, path, query, fragment = _uri_split(iri)

    scheme = to_native(scheme, 'ascii')
    if not isinstance(hostname, str) and six.PY3:
        hostname = to_native(hostname, 'ascii')
    hostname = to_native(hostname.encode('idna'), 'ascii')
    if auth:
        auth = to_native(auth, charset)
        if ':' in auth:
            auth, password = auth.split(':', 1)
        else:
            password = None
        auth = to_native(url_quote(auth), charset)
        if password:
            auth += ':' + to_native(url_quote(password))
        hostname = auth + '@' + hostname
    if port:
        hostname += ':' + to_native(port, 'ascii')

    path = to_native(url_quote(path, safe="/:~+%"))
    if isinstance(query, bytes):
        query = url_quote(query, safe="=%&[]:;$()+,!?*/")
    else:
        query = url_quote(query, safe="=%&[]:;$()+,!?*/", encoding=charset)
    query = to_native(query, charset)
    fragment = to_native(fragment, charset)

    # this absolutely always must return a string.  Otherwise some parts of
    # the system might perform double quoting (#61)
    rv = urlparse.urlunsplit([scheme, hostname, path, query, fragment])
    assert isinstance(rv, str)
    return rv


def uri_to_iri(uri, charset='utf-8', errors='replace'):
    r"""Converts a URI in a given charset to a IRI.

    Examples for URI versus IRI

    >>> uri_to_iri(b'http://xn--n3h.net/')
    u'http://\u2603.net/'
    >>> uri_to_iri(b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th')
    u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th'

    Query strings are left unchanged:

    >>> uri_to_iri(b'/?foo=24&x=%26%2f')
    u'/?foo=24&x=%26%2f'

    .. versionadded:: 0.6

    :param uri: the URI to convert
    :param charset: the charset of the URI
    :param errors: the error handling on decode
    """
    uri = url_fix(uri, charset)
    scheme, auth, hostname, port, path, query, fragment = _uri_split(uri)

    if not six.PY3:
        scheme = _decode_unicode(scheme, 'ascii', errors)

    try:
        if six.PY3 and isinstance(hostname, six.text_type):
            hostname = hostname.encode(charset, errors)
        hostname = hostname.decode('idna')
    except UnicodeError:
        # dammit, that codec raised an error.  Because it does not support
        # any error handling we have to fake it.... badly
        if errors not in ('ignore', 'replace'):
            raise
        hostname = hostname.decode('ascii', errors)

    if auth:
        if ':' in auth:
            auth, password = auth.split(':', 1)
        else:
            password = None
        auth = url_unquote(auth, encoding=charset, errors=errors)
        if password:
            auth += u':' + url_unquote(password, encoding=charset, errors=errors)
        hostname = auth + u'@' + hostname
    if port:
        # port should be numeric, but you never know...
        hostname += u':' + port.decode(charset, errors)

    path = url_unquote(path, unsafe=b'/;?', encoding=charset, errors=errors)
    query = url_unquote(query, unsafe=b';/?:@&=+,$', encoding=charset, errors=errors)

    return urlparse.urlunsplit([scheme, hostname, path, query, fragment])


def url_decode(s, charset='utf-8', decode_keys=False, include_empty=True,
               errors='replace', separator=b'&', cls=None):
    """Parse a querystring and return it as :class:`MultiDict`.  Per default
    only values are decoded into unicode strings.  If `decode_keys` is set to
    `True` the same will happen for keys.

    Per default a missing value for a key will default to an empty key.  If
    you don't want that behavior you can set `include_empty` to `False`.

    Per default encoding errors are ignored.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.

    .. versionchanged:: 0.5
       In previous versions ";" and "&" could be used for url decoding.
       This changed in 0.5 where only "&" is supported.  If you want to
       use ";" instead a different `separator` can be provided.

       The `cls` parameter was added.

    :param s: a string with the query string to decode.
    :param charset: the charset of the query string.
    :param decode_keys: set to `True` if you want the keys to be decoded
                        as well.
    :param include_empty: Set to `False` if you don't want empty values to
                          appear in the dict.
    :param errors: the decoding error behavior.
    :param separator: the pair separator to be used, defaults to ``&``
    :param cls: an optional dict class to use.  If this is not specified
                       or `None` the default :class:`MultiDict` is used.
    """
    if cls is None:
        cls = MultiDict
    if not isinstance(s, six.binary_type):
        s = s.encode(charset)
    if not isinstance(separator, six.binary_type):
        separator = separator.encode(charset)
    return cls(_url_decode_impl(s.split(separator), charset, decode_keys,
                                include_empty, errors))


def url_decode_stream(stream, charset='utf-8', decode_keys=False,
                      include_empty=True, errors='replace', separator='&',
                      cls=None, limit=None, return_iterator=False):
    """Works like :func:`url_decode` but decodes a stream.  The behavior
    of stream and limit follows functions like
    :func:`~werkzeug.wsgi.make_line_iter`.  The generator of pairs is
    directly fed to the `cls` so you can consume the data while it's
    parsed.

    .. versionadded:: 0.8

    :param stream: a stream with the encoded querystring
    :param charset: the charset of the query string.
    :param decode_keys: set to `True` if you want the keys to be decoded
                        as well.
    :param include_empty: Set to `False` if you don't want empty values to
                          appear in the dict.
    :param errors: the decoding error behavior.
    :param separator: the pair separator to be used, defaults to ``&``
    :param cls: an optional dict class to use.  If this is not specified
                       or `None` the default :class:`MultiDict` is used.
    :param limit: the content length of the URL data.  Not necessary if
                  a limited stream is provided.
    :param return_iterator: if set to `True` the `cls` argument is ignored
                            and an iterator over all decoded pairs is
                            returned
    """
    if return_iterator:
        cls = lambda x: x
    elif cls is None:
        cls = MultiDict
    pair_iter = make_chunk_iter(stream, separator, limit)
    return cls(_url_decode_impl(pair_iter, charset, decode_keys,
                                include_empty, errors))


def _url_decode_impl(pair_iter, charset, decode_keys, include_empty,
                     errors):
    #XXX: review bytes vs unicode again
    for pair in pair_iter:
        if not pair:
            continue
        if isinstance(pair, six.binary_type):
            pair = pair.decode(charset, errors)
        if u'=' in pair:
            key, value = pair.split(u'=', 1)
        else:
            if not include_empty:
                continue
            key = pair
            value = u''
        key = url_unquote_plus(key, encoding=charset, errors=errors)
        value = url_unquote_plus(value, encoding=charset, errors=errors)
        # decode_keys is ignored for similar reasons
        # stated in _url_encode_impl
        yield key, value


def url_encode(obj, charset='utf-8', encode_keys=False, sort=False, key=None,
               separator=u'&'):
    """URL encode a dict/`MultiDict`.  If a value is `None` it will not appear
    in the result string.  Per default only values are encoded into the target
    charset strings.  If `encode_keys` is set to ``True`` unicode keys are
    supported too.

    If `sort` is set to `True` the items are sorted by `key` or the default
    sorting algorithm.

    .. versionadded:: 0.5
        `sort`, `key`, and `separator` were added.

    :param obj: the object to encode into a query string.
    :param charset: the charset of the query string.
    :param encode_keys: set to `True` if you have unicode keys.
    :param sort: set to `True` if you want parameters to be sorted by `key`.
    :param separator: the separator to be used for the pairs.
    :param key: an optional function to be used for sorting.  For more details
                check out the :func:`sorted` documentation.
    """
    return separator.join(_url_encode_impl(obj, charset, encode_keys, sort, key))


def url_encode_stream(obj, stream=None, charset='utf-8', encode_keys=False,
                      sort=False, key=None, separator='&'):
    """Like :meth:`url_encode` but writes the results to a stream
    object.  If the stream is `None` a generator over all encoded
    pairs is returned.

    .. versionadded:: 0.8

    :param obj: the object to encode into a query string.
    :param stream: a stream to write the encoded object into or `None` if
                   an iterator over the encoded pairs should be returned.  In
                   that case the separator argument is ignored.
    :param charset: the charset of the query string.
    :param encode_keys: set to `True` if you have unicode keys.
    :param sort: set to `True` if you want parameters to be sorted by `key`.
    :param separator: the separator to be used for the pairs.
    :param key: an optional function to be used for sorting.  For more details
                check out the :func:`sorted` documentation.
    """
    gen = _url_encode_impl(obj, charset, encode_keys, sort, key)
    if stream is None:
        return gen
    for idx, chunk in enumerate(gen):
        if idx:
            stream.write(separator)
        stream.write(chunk)


def _url_encode_impl(obj, charset, encode_keys, sort, key):
    #XXX: probably broken badly on 3.x
    iterable = iter_multi_items(obj)
    iterable = ((to_bytes(k, charset), to_bytes(v, charset))
                for k, v in iterable if v is not None)
    if sort:
        iterable = sorted(iterable, key=key)
    # we need to ignore encode_keys, because quote takes nothing else than
    # bytes
    return (u'%s=%s' % (url_quote(k), url_quote_plus(v))
            for k, v in iterable)


def url_fix(s, charset='utf-8'):
    r"""Sometimes you get an URL by a user that just isn't a real URL because
    it contains unsafe characters like ' ' and so on.  This function can fix
    some of the problems in a similar way browsers handle data entered by the
    user:

    >>> url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffskl\xe4rung)')
    'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

    :param s: the string with the URL to fix.
    :param charset: The target charset for the URL if the url was given as
                    unicode string.
    """
    if not isinstance(s, six.text_type):
        s = s.decode(charset)
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = url_quote(path, safe='/%')
    qs = url_quote_plus(qs, safe=':&%=')
    parts = (scheme, netloc, path, qs, anchor)
    #print(repr(parts))
    return to_native(urlparse.urlunsplit(parts), charset)


class Href(object):
    """Implements a callable that constructs URLs with the given base. The
    function can be called with any number of positional and keyword
    arguments which than are used to assemble the URL.  Works with URLs
    and posix paths.

    Positional arguments are appended as individual segments to
    the path of the URL:

    >>> href = Href(u'/foo')
    >>> href(u'bar', 23)
    u'/foo/bar/23'
    >>> href(u'foo', bar=23)
    u'/foo/foo?bar=23'

    If any of the arguments (positional or keyword) evaluates to `None` it
    will be skipped.  If no keyword arguments are given the last argument
    can be a :class:`dict` or :class:`MultiDict` (or any other dict subclass),
    otherwise the keyword arguments are used for the query parameters, cutting
    off the first trailing underscore of the parameter name:

    >>> href(is_=42)
    u'/foo?is=42'
    >>> href({u'foo': u'bar'})
    u'/foo?foo=bar'

    Combining of both methods is not allowed:

    >>> href({u'foo': u'bar'}, bar=42)
    Traceback (most recent call last):
      ...
    TypeError: keyword arguments and query-dicts can't be combined

    Accessing attributes on the href object creates a new href object with
    the attribute name as prefix:

    >>> bar_href = href.bar
    >>> bar_href(u"blub")
    u'/foo/bar/blub'

    If `sort` is set to `True` the items are sorted by `key` or the default
    sorting algorithm:

    >>> href = Href("u/", sort=True)
    >>> href(a=1, b=2, c=3)
    u'/?a=1&b=2&c=3'

    .. versionadded:: 0.5
        `sort` and `key` were added.
    """

    def __init__(self, base=u'./', charset='utf-8', sort=False, key=None):
        if not base:
            base = u'./'
        self.base = base
        self.charset = charset
        self.sort = sort
        self.key = key

    def __getattr__(self, name):
        if name[:2] == '__':
            raise AttributeError(name)
        base = self.base
        if base[-1:] != u'/':
            base += u'/'
        if isinstance(name, bytes):
            name = name.decode(self.charset)
        return Href(urlparse.urljoin(base, name), self.charset, self.sort,
                    self.key)

    def __quote(self, part):
        return url_quote(part, encoding=self.charset)

    def __call__(self, *path, **query):
        #XXX: Badly broken on Py3
        if path and isinstance(path[-1], dict):
            if query:
                raise TypeError('keyword arguments and query-dicts '
                                'can\'t be combined')
            query, path = path[-1], path[:-1]
        elif query:
            query = dict([(k.endswith(u'_') and k[:-1] or k, v)
                          for k, v in query.items()])
        path = u'/'.join(map(self.__quote, filter(None, path))).lstrip('/')
        rv = self.base
        if path:
            if not rv.endswith(u'/'):
                rv += u'/'
            rv = urlparse.urljoin(rv, u'./' + path)
        if query:
            rv += u'?' + url_encode(query, self.charset, sort=self.sort,
                                   key=self.key)
        return rv
