# -*- coding: utf-8 -*-
"""
    werkzeug.urls
    ~~~~~~~~~~~~~

    This module implements various URL related functions.

    Parts of this module are based on the Lib/urllib/parse.py module of the
    Python 3.x standard library, licensed under the `PSF 2 License`_ using the
    following copyright notice::

        Copyright © 2001-2013 Python Software Foundation; All Rights Reserved

    .. _PSF 2 License: http://docs.python.org/3/license.html

    :copyright: (c) 2013 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re

from werkzeug._compat import text_type, xrange, PY2, to_native, to_unicode, \
    int2byte, string_types, imap
from werkzeug.datastructures import MultiDict, iter_multi_items


#: Characters valid in scheme names
SCHEME_CHARS = frozenset(
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    '+-.'
)

#: Characters that are safe in any part of an URL.
ALWAYS_SAFE = frozenset(
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    '_.-'
)

#: Schemes that use a netloc as part of their URL.
USES_NETLOC = frozenset([
    'ftp', 'http', 'gopher', 'nntp', 'telnet', 'imap', 'wais', 'file', 'mms',
    'https', 'shttp', 'snews', 'prospero', 'rtsp', 'rtspu', 'rsync', '', 'svn',
    'svn+ssh', 'sftp', 'nfs', 'git', 'git+ssh'
])

#: Schemes that use relative paths as part of their URL.
USES_RELATIVE = frozenset([
    'ftp', 'http', 'gopher', 'nntp', 'imap', 'wais', 'file', 'https', 'shttp',
    'mms', 'prospero', 'rtsp', 'rtspu', '', 'sftp', 'svn', 'svn+ssh'
])

#: Schemes that use params as part of their URL.
USES_PARAMS = frozenset([
    'ftp', 'hdl', 'prospero', 'http', 'imap', 'https', 'shttp', 'rtsp',
    'rtspu', 'sip', 'sips', 'mms', '', 'sftp', 'tel'
])


def _splitnetloc(iri, start=0):
    delim = len(iri) # position of end of domain part of iri, default is end
    for c in '/?#':  # look for delimiters; the order is NOT important
        wdelim = iri.find(c, start)      # find first of this delim
        if wdelim >= 0:                  # if found
            delim = min(delim, wdelim)   # use earliest delim position
    return iri[start:delim], iri[delim:] # return (domain, rest)


def irisplit(iri, scheme=u'', allow_fragments=True):
    if not (isinstance(iri, text_type) and isinstance(scheme, text_type)):
        raise TypeError('iri and scheme must be bytes')
    netloc = query = fragment = u''
    i = iri.find(u':')
    if i > 0:
        if iri[:i] == u'http': # optimize the common case
            scheme = iri[:i].lower()
            iri = iri[i+1:]
            if iri[:2] == u'//':
                netloc, iri = _splitnetloc(iri, 2)
                if ((u'[' in netloc and u']' not in netloc) or
                    (u']' in netloc and u'[' not in netloc)):
                    raise ValueError('Invalid IPv6 URL')
            if allow_fragments and u'#' in iri:
                iri, fragment = iri.split(u'#', 1)
            if u'?' in iri:
                iri, query = iri.split(u'?', 1)
            return scheme, netloc, iri, query, fragment
        for c in iri[:i]:
            if c not in SCHEME_CHARS:
                break
        else:
            # make sure "iri" is not actually a port number (in which case
            # "scheme" is really part of the path)
            rest = iri[i+1:]
            if not rest or any(c not in u'0123456789' for c in rest):
                # not a port number
                scheme, iri = iri[:i].lower(), rest

    if iri[:2] == u'//':
        netloc, iri = _splitnetloc(iri, 2)
        if ((u'[' in netloc and u']' not in netloc) or
            (u']' in netloc and u'[' not in netloc)):
            raise ValueError('Invalid IPv6 URL')
    if allow_fragments and u'#' in iri:
        iri, fragment = iri.split(u'#', 1)
    if u'?' in iri:
        url, query = iri.split(u'?', 1)
    return scheme, netloc, iri, query, fragment


def urisplit(uri, scheme=b'', allow_fragments=True):
    if not (isinstance(uri, bytes) and isinstance(scheme, bytes)):
        raise TypeError('uri and scheme must be bytes')
    return tuple(component.encode('ascii') for component in irisplit(
        uri.decode('ascii'),
        scheme.decode('ascii'),
        allow_fragments
    ))


def urlsplit(url, scheme='', allow_fragments=True):
    # XXX: ascii -> default encoding?
    if isinstance(url, text_type):
        if not isinstance(scheme, text_type):
            scheme = scheme.decode('ascii')
        return irisplit(url, scheme, allow_fragments)
    elif isinstance(url, bytes):
        if not isinstance(scheme, bytes):
            scheme = scheme.encode('ascii')
        return urisplit(url, scheme, allow_fragments)
    else:
        raise TypeError('url must be a string')


def url_quote(string, safe='/', charset='utf-8', errors='strict'):
    """URL encode a single string with a given encoding.

    :param s: the string to quote.
    :param charset: the charset to be used.
    :param safe: an optional sequence of safe characters.
    """
    return quote(string, safe, charset, errors)


def quote(string, safe='/', charset='utf-8', errors='strict'):
    if isinstance(string, text_type):
        string = string.encode(charset, errors)
    safe = set(
        int2byte(char) if isinstance(char, int) else char
        for char in ALWAYS_SAFE.union(safe)
    )
    safe = set(b"".join(
        char.encode(charset, 'replace') if hasattr(char, 'encode') else char
        for char in safe
    ))
    return b''.join(
        char if char in safe else ('%%%X' % ord(char)).encode('ascii')
        for char in imap(int2byte, bytearray(string))
    )


def url_quote_plus(string, charset='utf-8', safe=''):
    """URL encode a single string with the given encoding and convert
    whitespace to "+".

    :param s: The string to quote.
    :param charset: The charset to be used.
    :param safe: An optional sequence of safe characters.
    """
    return url_quote(string, set(safe).union([' ']), charset).replace(b' ', b'+')


def urlunsplit(components):
    if all(isinstance(component, text_type) for component in components):
        return iriunsplit(components)
    elif all(isinstance(component, bytes) for component in components):
        return uriunsplit(components)
    raise TypeError('mixed type components: %r' % components)


def iriunsplit(components):
    if not all(isinstance(component, text_type) for component in components):
        raise TypeError('expected unicode components: %r' % components)
    scheme, netloc, url, query, fragment = components
    if netloc or (scheme and scheme in USES_NETLOC and url[:2] != u'//'):
        if url and url[:1] != u'/':
            url = u'/' + url
        url = u'//' + (netloc or u'') + url
    if scheme:
        url = scheme + u':' + url
    if query:
        url = url + u'?' + query
    if fragment:
        url = url + u'#' + fragment
    return url


def uriunsplit(components):
    if not all(isinstance(component, bytes) for component in components):
        raise TypeError('expected bytes components: %r' % components)
    return iriunsplit(
        [component.decode('ascii') for component in components]
    ).encode('ascii')


def _url_split(url):
    scheme, netloc, path, query, fragment = urlsplit(url)

    if isinstance(netloc, text_type) and u'@' in netloc:
        auth, hostname = netloc.split(u'@', 1)
    elif isinstance(netloc, bytes) and b'@' in netloc:
        auth, hostname = netloc.split(u'b', 1)
    else:
        auth = None
        hostname = netloc

    port = None
    if hostname:
        if isinstance(hostname, text_type) and u':' in hostname:
            hostname, port = hostname.split(u':', 1)
        elif isinstance(hostname, bytes) and b':' in hostname:
            hostname, port = hostname.split(b':', 1)
    return scheme, auth, hostname, port, path, query, fragment


def iri_to_uri(iri, charset='utf-8', errors='strict'):
    r"""
    Converts any unicode based IRI to an acceptable ASCII URI. Werkzeug always
    uses utf-8 URLs internally because this is what browsers and HTTP do as
    well. In some places where it accepts an URL it also accepts a unicode IRI
    and converts it into a URI.

    Examples for IRI versus URI:

    >>> iri_to_uri(u'http://☃.net/')
    'http://xn--n3h.net/'
    >>> iri_to_uri(u'http://üser:pässword@☃.net/påth')
    'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th'

    .. versionadded:: 0.6

    :param iri: The IRI to convert.
    :param charset: The charset for the URI.
    """
    if isinstance(iri, bytes):
        iri = iri.decode('ascii') # iri is really an uri
    scheme, auth, hostname, port, path, query, fragment = _url_split(iri)

    scheme = scheme.encode(charset, errors)
    hostname = hostname.encode('idna')

    if auth:
        if u':' in auth:
            auth, password = auth.split(':', 1)
        else:
            password = None
        auth = url_quote(auth, charset, errors)
        if password:
            auth += b':' + url_quote(password, charset, errors)
        hostname += auth + b'@' + hostname
    if port:
        hostname += b':' + port.encode(charset, errors)

    path = url_quote(path, '/:~+%', charset, errors)
    query = url_quote(query, '%&[]:;$*()+,!?*/', charset, errors)
    fragment = url_quote(fragment, '=%&[]:;$()+,!?*/', charset, errors)

    return urlunsplit((scheme, hostname, path, query, fragment))


_hexdigits = '0123456789ABCDEFabcdef'
_hextobyte = dict(
    ((a + b).encode(), int2byte(int(a + b, 16)))
    for a in _hexdigits for b in _hexdigits
)
def unquote_to_bytes(string, unsafe=''):
    if isinstance(string, text_type):
        string = string.encode('utf-8')
    if isinstance(unsafe, text_type):
        unsafe = unsafe.encode('utf-8')
    unsafe = frozenset(unsafe)
    bits = string.split(b'%')
    result = [bits[0]]
    for item in bits[1:]:
        try:
            char = _hextobyte[item[:2]]
            if char in unsafe:
                raise KeyError()
            result.append(char)
            result.append(item[2:])
        except KeyError:
            result.append(b'%')
            result.append(item)
    return b''.join(result)


_ascii_re = re.compile(to_unicode(r'([\x00-\x7f]+)', 'ascii'))
def url_unquote(string, charset='utf-8', errors='replace', unsafe=''):
    """URL decode a single string with a given decoding.

    Per default encoding errors are ignored.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.

    :param s: the string to unquote.
    :param charset: the charset to be used.
    :param errors: the error handling for the charset decoding.
    """
    if isinstance(string, bytes):
        string = string.decode('ascii') # uri -> iri
    bits = _ascii_re.split(string)
    result = [bits[0]]
    for i in xrange(1, len(bits), 2):
        result.append(unquote_to_bytes(bits[i], unsafe).decode(charset, errors))
        result.append(bits[i + 1])
    return u''.join(result)


def url_unquote_plus(s, charset='utf-8', errors='replace'):
    """URL decode a single string with the given `charset` and decode "+" to
    whitespace.

    Per default encoding errors are ignored.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    :exc:`HTTPUnicodeError` is raised.

    :param s: The string to unquote.
    :param charsert: The charset to be used.
    :param errors: The error handling for the `charset` decoding.
    """
    if isinstance(s, text_type):
        s = s.replace(u'+', u' ')
    else:
        s = s.replace(b'+', b' ')
    return url_unquote(s, charset, errors)


def url_fix(s, charset='utf-8'):
    if isinstance(s, text_type):
        s = s.encode(charset, 'replace')
    scheme, netloc, path, qs, anchor = urlsplit(s)
    path = url_quote(path, safe='/%')
    qs = url_quote_plus(path, safe=':&%=')
    return urlunsplit((scheme, netloc, path, qs, anchor))


def uri_to_iri(uri, charset='utf-8', errors='replace'):
    r"""
    Converts a URI in a given charset to a IRI.

    Examples for URI versus IRI:

    >>> uri_to_iri(b'http://xn--n3h.net/')
    u'http://\u2603.net/'
    >>> uri_to_iri(b'http://%C3%BCser:p%C3%A4ssword@xn--n3h.net/p%C3%A5th')
    u'http://\xfcser:p\xe4ssword@\u2603.net/p\xe5th'

    Query strings are left unchanged:

    >>> uri_to_iri('/?foo=24&x=%26%2f')
    u'/?foo=24&x=%26%2f'

    .. versionadded:: 0.6

    :param uri: The URI to convert.
    :param charset: The charset of the URI.
    :param errors: The error handling on decode.
    """
    if isinstance(uri, text_type):
        uri = uri.encode('ascii') # iri -> uri
    uri = url_fix(uri)
    scheme, auth, hostname, port, path, query, fragment = _url_split(uri)

    scheme = scheme.decode(charset, errors)
    hostname = hostname.decode('idna')

    if auth:
        if b':' in auth:
            auth, password = auth.split(b':', 1)
        else:
            password = None
        auth = url_unquote(auth, charset, errors)
        if password:
            auth += u':' + url_unquote(password, charset, errors)
        hostname = auth + u'@' + hostname

    if port:
        hostname += u':' + port.decode(charset, errors)

    path = url_unquote(path, charset, errors, '/;?')
    query = url_unquote(query, charset, errors, ';/?:@&=+,$')
    fragment = url_unquote(fragment, charset, errors, ';/?:@&=+,$')
    return urlunsplit((scheme, hostname, path, query, fragment))


def url_decode(s, charset='utf-8', decode_keys=False, include_empty=True,
               errors='replace', separator='&', cls=None):
    """
    Parse a querystring and return it as :class:`MultiDict`.  Per default
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
    if isinstance(s, text_type) and not isinstance(separator, text_type):
        separator = separator.decode('ascii')
    elif isinstance(s, bytes) and not isinstance(separator, bytes):
        separator = separator.encode('ascii')
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
                        as well. (Ignored on Python 3.x)
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
    from werkzeug.wsgi import make_chunk_iter
    if return_iterator:
        cls = lambda x: x
    elif cls is None:
        cls = MultiDict
    pair_iter = make_chunk_iter(stream, separator, limit)
    return cls(_url_decode_impl(pair_iter, charset, decode_keys,
                                include_empty, errors))


def _url_decode_impl(pair_iter, charset, decode_keys, include_empty, errors):
    for pair in pair_iter:
        if not pair:
            continue
        if isinstance(pair, bytes):
            pair = pair.decode('ascii')
        if u'=' in pair:
            key, value = pair.split(u'=', 1)
        else:
            if not include_empty:
                continue
            key = pair
            value = u''
        key = url_unquote_plus(key, charset, errors)
        if PY2 and not decode_keys:
            # Force key into a native string.
            key = key.encode('ascii')
        yield key, url_unquote_plus(value, charset, errors)


def url_encode(obj, charset='utf-8', encode_keys=False, sort=False, key=None,
               separator=b'&'):
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
    :param encode_keys: set to `True` if you have unicode keys. (Ignored on
                        Python 3.x)
    :param sort: set to `True` if you want parameters to be sorted by `key`.
    :param separator: the separator to be used for the pairs.
    :param key: an optional function to be used for sorting.  For more details
                check out the :func:`sorted` documentation.
    """
    return separator.join(_url_encode_impl(obj, charset, encode_keys, sort, key))


def url_encode_stream(obj, stream=None, charset='utf-8', encode_keys=False,
                      sort=False, key=None, separator=b'&'):
    """Like :meth:`url_encode` but writes the results to a stream
    object.  If the stream is `None` a generator over all encoded
    pairs is returned.

    .. versionadded:: 0.8

    :param obj: the object to encode into a query string.
    :param stream: a stream to write the encoded object into or `None` if
                   an iterator over the encoded pairs should be returned.  In
                   that case the separator argument is ignored.
    :param charset: the charset of the query string.
    :param encode_keys: set to `True` if you have unicode keys. (Ignored on
                        Python 3.x)
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
    iterable = iter_multi_items(obj)
    if sort:
        iterable = sorted(iterable, key=key)
    for key, value in iterable:
        if value is None:
            continue
        if PY2 and not encode_keys:
            # Force coercion-like behavior on native strings
            key = url_quote(key, 'ascii')
        else:
            key = url_quote(str(key), charset)
        if not isinstance(value, string_types):
            value = str(value)
        yield key + b"=" + url_quote_plus(value)


def _splitparams(iri):
    if u'/' in iri:
        i = iri.find(u';', iri.rfind(u'/'))
        if i < 0:
            return iri, u''
    else:
        i = iri.find(u';')
    return iri[:i], iri[i+1:]


def iriparse(iri, scheme=u'', allow_fragments=True):
    scheme, netloc, url, query, fragment = urlsplit(iri, scheme, allow_fragments)
    if scheme in USES_PARAMS and u';' in iri:
        iri, params = _splitparams(iri)
    else:
        params = u''
    return scheme, netloc, url, params, query, fragment


def uriparse(uri, scheme=b'', allow_fragments=True):
    return tuple(component.encode('ascii') for component in iriparse(
        uri.decode('ascii'),
        scheme.decode('ascii'),
        allow_fragments
    ))


def urlparse(url, scheme='', allow_fragments=True):
    """Parse a URL into 6 components:
    <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    Return a 6-tuple: (scheme, netloc, path, params, query, fragment).
    Note that we don't break the components up in smaller bits
    (e.g. netloc is a single string) and we don't expand % escapes."""
    # XXX: ascii -> default encoding?
    if isinstance(url, text_type):
        if not isinstance(scheme, text_type):
            scheme = scheme.decode('ascii')
        return iriparse(url, scheme, allow_fragments)
    elif isinstance(url, bytes):
        if not isinstance(scheme, bytes):
            scheme = scheme.encode('ascii')
        return uriparse(url, scheme, allow_fragments)
    raise TypeError('url must be a string: %r' % url)


def iriunparse(components):
    if not all(isinstance(component, text_type) for component in components):
        raise TypeError('expected unicode components: %r' % components)
    scheme, netloc, iri, params, query, fragment = components
    if params:
        iri = u'%s;%s' % (iri, params)
    return urlunsplit((scheme, netloc, iri, query, fragment))


def uriunparse(components):
    if not all(isinstance(component, bytes) for component in components):
        raise TypeError('expected bytes components: %r' % components)
    return iriunparse(
        [component.decode('ascii') for component in components]
    ).encode('ascii')


def urlunparse(components):
    """Put a parsed URL back together again. This may result in a slightly
    different, but equivalent URL, if the URL that was parsed originally had
    redundant delimiters, e.g. a ? with an empty query (the draft states that
    these are equivalent)."""
    if all(isinstance(component, text_type) for component in components):
        return iriunparse(components)
    elif all(isinstance(component, text_type) for component in components):
        return uriunparse(components)
    else:
        raise TypeError('mixed type components: %r' % components)


def urljoin(base, url, allow_fragments=True):
    """Join a base URL and a possibly relative URL to form an absolute
    interpretation of the latter."""
    if isinstance(base, text_type) and isinstance(url, text_type):
        return irijoin(base, url, allow_fragments)
    elif isinstance(base, bytes) and isinstance(url, bytes):
        return urijoin(base, url, allow_fragments)
    raise TypeError('base and url have different types')


def urijoin(base, url, allow_fragments=True):
    if not (isinstance(base, bytes) and isinstance(url, bytes)):
        raise TypeError('base and url must be bytes')
    return irijoin(base.decode('ascii'), url.decode('ascii')).encode('ascii')


def irijoin(base, url, allow_fragments=True):
    if not (isinstance(base, text_type) and isinstance(url, text_type)):
        raise TypeError('base and url must be unicode')
    if not base:
        return url
    if not url:
        return base
    bscheme, bnetloc, bpath, bparams, bquery, bfragment = \
        urlparse(base, u'', allow_fragments)
    scheme, netloc, path, params, query, fragment = \
        urlparse(base, bscheme, allow_fragments)
    if scheme != bscheme or scheme not in USES_RELATIVE:
        return url
    if scheme in USES_NETLOC:
        if netloc:
            return urlunparse((scheme, netloc, path, params, query, fragment))

        netloc = bnetloc
    if path[:1] == u'/':
        return urlunparse((scheme, netloc, path, params, query, fragment))

    if not path and not params:
        path = bpath
        params = bparams
        if not query:
            query = bquery
        return urlunparse((scheme, netloc, path, params, query, fragment))
    segments = bpath.split(u'/')[:-1] + path.split(u'/')
    # XXX The stuff below is bogus in various ways...
    if segments[-1] == u'.':
        segments[-1] = u''
    while u'.' in segments:
        segments.remove(u'.')
    while True:
        i = 1
        n = len(segments) - 1
        while i < n:
            if (segments[i] == u'..'
                and segments[i-1] not in (u'', u'..')):
                del segments[i-1:i+1]
                break
            i = i + 1
        else:
            break
    if segments == [u'', u'..']:
        segments[-1] = ''
    elif len(segments) >= 2 and segments[-1] == u'..':
        segments[-2:] = [u'']
    return urlunparse((scheme, netloc, u'/'.join(segments), params, query,
                       fragment))


class Href(object):
    """Implements a callable that constructs URLs with the given base. The
    function can be called with any number of positional and keyword
    arguments which than are used to assemble the URL.  Works with URLs
    and posix paths.

    Positional arguments are appended as individual segments to
    the path of the URL:

    >>> href = Href('/foo')
    >>> href('bar', 23)
    '/foo/bar/23'
    >>> href('foo', bar=23)
    '/foo/foo?bar=23'

    If any of the arguments (positional or keyword) evaluates to `None` it
    will be skipped.  If no keyword arguments are given the last argument
    can be a :class:`dict` or :class:`MultiDict` (or any other dict subclass),
    otherwise the keyword arguments are used for the query parameters, cutting
    off the first trailing underscore of the parameter name:

    >>> href(is_=42)
    '/foo?is=42'
    >>> href({'foo': 'bar'})
    '/foo?foo=bar'

    Combining of both methods is not allowed:

    >>> href({'foo': 'bar'}, bar=42)
    Traceback (most recent call last):
      ...
    TypeError: keyword arguments and query-dicts can't be combined

    Accessing attributes on the href object creates a new href object with
    the attribute name as prefix:

    >>> bar_href = href.bar
    >>> bar_href("blub")
    '/foo/bar/blub'

    If `sort` is set to `True` the items are sorted by `key` or the default
    sorting algorithm:

    >>> href = Href("/", sort=True)
    >>> href(a=1, b=2, c=3)
    '/?a=1&b=2&c=3'

    .. versionadded:: 0.5
        `sort` and `key` were added.
    """

    def __init__(self, base='./', charset='utf-8', sort=False, key=None):
        if not base:
            base = './'
        self.base = base
        self.charset = charset
        self.sort = sort
        self.key = key

    def __getattr__(self, name):
        if name[:2] == '__':
            raise AttributeError(name)
        base = self.base
        if base[-1:] != '/':
            base += '/'
        return Href(urljoin(base, name), self.charset, self.sort, self.key)

    def __call__(self, *path, **query):
        if path and isinstance(path[-1], dict):
            if query:
                raise TypeError('keyword arguments and query-dicts '
                                'can\'t be combined')
                query, path = path[-1], path[:-1]
        elif query:
            query = dict([(k.endswith('_') and k[:-1] or k, v)
                          for k, v in query.items()])
        path = '/'.join([to_native(url_quote(x, self.charset))
                         for x in path if x is not None]).lstrip('/')
        rv = self.base
        if path:
            if not rv.endswith('/'):
                rv += '/'
            rv = urljoin(rv, './' + path)
        if query:
            rv += '?' + to_native(url_encode(query, self.charset,
                                             sort=self.sort, key=self.key))
        return rv
