# -*- coding: utf-8 -*-
"""
    werkzeug.http
    ~~~~~~~~~~~~~

    Werkzeug comes with a bunch of utilties that help Werkzeug to deal with
    HTTP data.  Most of the classes and functions provided by this module are
    used by the wrappers, but they are useful on their own too, especially if
    the response and request objects are not used.

    This covers some of the more HTTP centric features of WSGI, some other
    utilities such as cookie handling are documented in the `werkzeug.utils`
    module.


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import re
import rfc822
from urllib2 import parse_http_list as _parse_list_header
from datetime import datetime
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
try:
    set = set
    frozenset = frozenset
except NameError:
    from sets import Set as set, ImmutableSet as frozenset
from werkzeug._internal import _patch_wrapper, _UpdateDict, HTTP_STATUS_CODES


_accept_re = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')
_token_chars = frozenset("!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                         '^_`abcdefghijklmnopqrstuvwxyz|~')
_etag_re = re.compile(r'([Ww]/)?(?:"(.*?)"|(.*?))(?:\s*,\s*|$)')


class Accept(list):
    """An `Accept` object is just a list subclass for lists of
    ``(value, quality)`` tuples.  It is automatically sorted by quality.
    """

    def __init__(self, values=()):
        if values is None:
            list.__init__(self)
            self.provided = False
        else:
            self.provided = True
            values = [(a, b) for b, a in values]
            values.sort()
            values.reverse()
            list.__init__(self, [(a, b) for b, a in values])

    def __getitem__(self, key):
        """Beside index lookup (getting item n) you can also pass it a string
        to get the quality for the item.  If the item is not in the list, the
        returned quality is ``0``.
        """
        if isinstance(key, basestring):
            for value in self:
                if value[0] == key:
                    return value[1]
            return 0
        return list.__getitem__(self, key)

    def __contains__(self, key):
        return self.find(key) > -1

    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__,
            list.__repr__(self)
        )

    def index(self, key):
        """Get the position of en entry or raise `IndexError`."""
        rv = self.find(key)
        if rv < 0:
            raise IndexError(key)
        return key

    def find(self, key):
        """Get the position of an entry or return -1"""
        if isinstance(key, basestring):
            for idx, value in enumerate(self):
                if value[0] == key:
                    return idx
            return -1
        return list.find(self, key)

    def values(self):
        """Return a list of the values, not the qualities."""
        return [x[0] for x in self]

    def itervalues(self):
        """Iterate over all values."""
        for item in self:
            yield item[0]

    def best(self):
        """The best match as value."""
        return self and self[0][0] or None
    best = property(best)


class HeaderSet(object):
    """Similar to the `ETags` class this implements a set like structure.
    Unlike `ETags` this is case insensitive and used for vary, allow, and
    content-language headers.

    If not constructed using the `parse_set_header` function the instanciation
    works like this:

    >>> hs = HeaderSet(['foo', 'bar', 'baz'])
    >>> hs
    HeaderSet(['foo', 'bar', 'baz'])
    """

    def __init__(self, headers=None, on_update=None):
        self._headers = list(headers or ())
        self._set = set([x.lower() for x in self._headers])
        self.on_update = on_update

    def add(self, header):
        """Add a new header to the set."""
        self.update((header,))

    def remove(self, header):
        """Remove a layer from the set.  This raises an `IndexError` if the
        header is not in the set."""
        key = header.lower()
        if key not in self._set:
            raise IndexError(header)
        self._set.remove(key)
        for idx, key in enumerate(self._headers):
            if key.lower() == header:
                del self._headers[idx]
                break
        if self.on_update is not None:
            self.on_update(self)

    def update(self, iterable):
        """Add all the headers from the iterable to the set."""
        inserted_any = False
        for header in iterable:
            key = header.lower()
            if key not in self._set:
                self._headers.append(header)
                self._set.add(key)
                inserted_any = True
        if inserted_any and self.on_update is not None:
            self.on_update(self)

    def discard(self, header):
        """Like remove but ignores errors."""
        try:
            return self.remove(header)
        except IndexError:
            pass

    def find(self, header):
        """Return the index of the header in the set or return -1 if not found."""
        header = header.lower()
        for idx, item in enumerate(self._headers):
            if item.lower() == header:
                return idx
        return -1

    def index(self, header):
        """Return the index of the headerin the set or raise an `IndexError`."""
        rv = self.find(header)
        if rv < 0:
            raise IndexError(header)
        return rv

    def clear(self):
        """Clear the set."""
        self._set.clear()
        del self._headers[:]
        if self.on_update is not None:
            self.on_update(self)

    def as_set(self, preserve_casing=False):
        """Return the set as real python set structure.  When calling this
        all the items are converted to lowercase and the ordering is lost.

        If `preserve_casing` is `True` the items in the set returned will
        have the original case like in the `HeaderSet`, otherwise they will
        be lowercase.
        """
        if preserve_casing:
            return set(self._headers)
        return set(self._set)

    def to_header(self):
        """Convert the header set into an HTTP header string."""
        return ', '.join(map(quote_header_value, self._headers))

    def __getitem__(self, idx):
        return self._headers[idx]

    def __delitem__(self, idx):
        rv = self._headers.pop(idx)
        self._set.remove(rv.lower())
        if self.on_update is not None:
            self.on_update(self)

    def __setitem__(self, idx, value):
        old = self._headers[idx]
        self._set.remove(old.lower())
        self._headers[idx] = value
        self._set.add(value.lower())
        if self.on_update is not None:
            self.on_update(self)

    def __contains__(self, header):
        return header.lower() in self._set

    def __len__(self):
        return len(self._set)

    def __iter__(self):
        return iter(self._headers)

    def __nonzero__(self):
        return bool(self._set)

    def __str__(self):
        return self.to_header()

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self._headers
        )


class CacheControl(_UpdateDict):
    """Subclass of a dict that stores values for a Cache-Control header.  It
    has accesors for all the cache-control directives specified in RFC 2616.
    The class does not differentiate between request and response directives.

    Because the cache-control directives in the HTTP header use dashes the
    python descriptors use underscores for that.

    To get a header of the `CacheControl` object again you can convert the
    object into a string or call the `to_header()` function.  If you plan
    to subclass it and add your own items have a look at the sourcecode for
    that class.

    The following attributes are exposed:

    `no_cache`, `no_store`, `max_age`, `max_stale`, `min_fresh`,
    `no_transform`, `only_if_cached`, `public`, `private`, `must_revalidate`,
    `proxy_revalidate`, and `s_maxage`"""

    def cache_property(key, default, type):
        """Return a new property object for a cache header.  Useful if you
        want to add support for a cache extension in a subclass."""
        return property(lambda x: x._get_cache_value(key, default, type),
                        lambda x, v: x._set_cache_value(key, v, type),
                        'accessor for %r' % key)

    no_cache = cache_property('no-cache', '*', bool)
    no_store = cache_property('no-store', None, bool)
    max_age = cache_property('max-age', -1, int)
    max_stale = cache_property('max-stale', '*', int)
    min_fresh = cache_property('min-fresh', '*', int)
    no_transform = cache_property('no-transform', None, None)
    only_if_cached = cache_property('only-if-cached', None, bool)
    public = cache_property('public', None, bool)
    private = cache_property('private', '*', None)
    must_revalidate = cache_property('must-revalidate', None, bool)
    proxy_revalidate = cache_property('proxy-revalidate', None, bool)
    s_maxage = cache_property('s-maxage', None, None)

    def __init__(self, values=(), on_update=None):
        _UpdateDict.__init__(self, values or (), on_update)
        self.provided = values is not None

    def _get_cache_value(self, key, default, type):
        """Used internally be the accessor properties."""
        if type is bool:
            return key in self
        if key in self:
            value = self[key]
            if value is None:
                return default
            elif type is not None:
                try:
                    value = type(value)
                except ValueError:
                    pass
            return value

    def _set_cache_value(self, key, value, type):
        """Used internally be the accessor properties."""
        if type is bool:
            if value:
                self[key] = None
            else:
                self.pop(key, None)
        else:
            if value is not None:
                self[key] = value
            else:
                self.pop(key, None)

    def to_header(self):
        """Convert the stored values into a cache control header."""
        return dump_header(self)

    def __str__(self):
        return self.to_header()

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.to_header()
        )

    # make cache_property a staticmethod so that subclasses of
    # `CacheControl` can use it for new properties.
    cache_property = staticmethod(cache_property)


class ETags(object):
    """A set that can be used to check if one etag is present in a collection
    of etags.
    """

    def __init__(self, strong_etags=None, weak_etags=None, star_tag=False):
        self._strong = frozenset(not star_tag and strong_etags or ())
        self._weak = frozenset(weak_etags or ())
        self.star_tag = star_tag

    def as_set(self, include_weak=False):
        """Convert the `ETags` object into a python set.  Per default all the
        weak etags are not part of this set."""
        rv = set(self._strong)
        if include_weak:
            rv.update(self._weak)
        return rv

    def is_weak(self, etag):
        """Check if an etag is weak."""
        return etag in self._weak

    def contains_weak(self, etag):
        """Check if an etag is part of the set including weak and strong tags."""
        return self.is_weak(etag) or self.contains(etag)

    def contains(self, etag):
        """Check if an etag is part of the set ignoring weak tags."""
        if self.star_tag:
            return True
        return etag in self._strong

    def contains_raw(self, etag):
        """When passed a quoted tag it will check if this tag is part of the
        set.  If the tag is weak it is checked against weak and strong tags,
        otherwise weak only."""
        etag, weak = unquote_etag(etag)
        if weak:
            return self.contains_weak(etag)
        return self.contains(etag)

    def to_header(self):
        """Convert the etags set into a HTTP header string."""
        if self.star_tag:
            return '*'
        return ', '.join(
            ['"%s"' % x for x in self._strong] +
            ['w/"%s"' % x for x in self._weak]
        )

    def __call__(self, etag=None, data=None, include_weak=False):
        if [etag, data].count(None) != 1:
            raise TypeError('either tag or data required, but at least one')
        if etag is None:
            etag = generate_etag(data)
        if include_weak:
            if etag in self._weak:
                return True
        return etag in self._strong

    def __nonzero__(self):
        return bool(self.star_tag or self._strong)

    def __str__(self):
        return self.to_header()

    def __iter__(self):
        return iter(self._strong)

    def __contains__(self, etag):
        return self.contains(etag)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, str(self))


class Authorization(dict):
    """Represents an `Authorization` header sent by the client.  You should
    not create this kind of object yourself but use it when it's returned by
    the `parse_authorization_header` function.

    This object is a dict subclass and can be altered by setting dict items
    but it should be considered immutable as it's returned by the client and
    not meant for modifications.
    """

    def __init__(self, auth_type, data=None):
        dict.__init__(self, data or {})
        self.type = auth_type

    username = property(lambda x: x.get('username'), doc='''
        The username transmitted.  This is set for both basic and digest
        auth all the time.''')
    password = property(lambda x: x.get('password'), doc='''
        When the authentication type is basic this is the password
        transmitted by the client, else `None`.''')
    realm = property(lambda x: x.get('realm'), doc='''
        This is the server realm send back for digest auth.  For HTTP
        digest auth.''')
    nonce = property(lambda x: x.get('nonce'), doc='''
        The nonce the server send for digest auth, send back by the client.
        A nonce should be unique for every 401 response for HTTP digest
        auth.''')
    uri = property(lambda x: x.get('uri'), doc='''
        The URI from Request-URI of the Request-Line; duplicated because
        proxies are allowed to change the Request-Line in transit.  HTTP
        digest auth only.''')
    nc = property(lambda x: x.get('nc'), doc='''
        The nonce count value transmitted by clients if a qop-header is
        also transmitted.  HTTP digest auth only.''')
    cnonce = property(lambda x: x.get('cnonce'), doc='''
        If the server sent a qop-header in the ``WWW-Authenticate``
        header, the client has to provide this value for HTTP digest auth.
        See the RFC for more details.''')
    response = property(lambda x: x.get('response'), doc='''
        A string of 32 hex digits computed as defined in RFC 2617, which
        proves that the user knows a password.  Digest auth only.''')
    opaque = property(lambda x: x.get('opaque'), doc='''
        The opaque header from the server returned unchanged by the client.
        It is recommended that this string be base64 or hexadecimal data.
        Digest auth only.''')

    def qop(self):
        """Indicates what "quality of protection" the client has applied to
        the message for HTTP digest auth."""
        def on_update(header_set):
            if not header_set and name in self:
                del self['qop']
            elif header_set:
                self['qop'] = header_set.to_header()
        return parse_set_header(self.get('qop'), on_update)
    qop = property(qop, doc=qop.__doc__)


class WWWAuthenticate(_UpdateDict):
    """Provides simple access to `WWW-Authenticate` headers."""

    #: list of keys that require quoting in the generated header
    _require_quoting = frozenset(['domain', 'nonce', 'opaque', 'realm'])

    def __init__(self, auth_type=None, values=None, on_update=None):
        _UpdateDict.__init__(self, values or (), on_update)
        if auth_type:
            self['__auth_type__'] = auth_type

    def set_basic(self, realm='authentication required'):
        """Clear the auth info and enable basic auth."""
        dict.clear(self)
        dict.update(self, {'__auth_type__': 'basic', 'realm': realm})
        if self.on_update:
            self.on_update(self)

    def set_digest(self, realm, nonce, qop=('auth',), opaque=None,
                   algorithm=None, stale=False):
        """Clear the auth info and enable digest auth."""
        d = {
            '__auth_type__':    'digest',
            'realm':            realm,
            'nonce':            nonce,
            'qop':              dump_header(qop)
        }
        if stale:
            d['stale'] = 'TRUE'
        if opaque is not None:
            d['opaque'] = opaque
        if algorithm is not None:
            d['algorithm'] = algorithm
        dict.clear(self)
        dict.update(self, d)
        if self.on_update:
            self.on_update(self)

    def to_header(self):
        """Convert the stored values into a WWW-Authenticate header."""
        d = dict(self)
        auth_type = d.pop('__auth_type__', None) or 'basic'
        return '%s %s' % (auth_type.title(), ', '.join([
            '%s=%s' % (key, quote_header_value(value,
                       allow_token=key not in self._require_quoting))
            for key, value in d.iteritems()
        ]))

    def __str__(self):
        return self.to_header()

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.to_header()
        )

    def auth_property(name, doc=None):
        def _set_value(self, value):
            if value is None:
                self.pop(name, None)
            else:
                self[name] = str(value)
        return property(lambda x: x.get(name), _set_value, doc=doc)

    def _set_property(name, doc=None):
        def fget(self):
            def on_update(header_set):
                if not header_set and name in self:
                    del self[name]
                elif header_set:
                    self[name] = header_set.to_header()
            return parse_set_header(self.get(name), on_update)
        return property(fget, doc=doc)

    type = auth_property('__auth_type__', doc='''
        The type of the auth machanism.  HTTP currently specifies
        `Basic` and `Digest`.''')
    realm = auth_property('realm', doc='''
        A string to be displayed to users so they know which username and
        password to use.  This string should contain at least the name of
        the host performing the authentication and might additionally
        indicate the collection of users who might have access.''')
    domain = _set_property('domain', doc='''
        A list of URIs that define the protection space.  If a URI is an
        absolte path, it is relative to the canonical root URL of the
        server being accessed.''')
    nonce = auth_property('nonce', doc='''
        A server-specified data string which should be uniquely generated
        each time a 401 response is made.  It is recommended that this
        string be base64 or hexadecimal data.''')
    opaque = auth_property('opaque', doc='''
        A string of data, specified by the server, which should be returned
        by the client unchanged in the Authorization header of subsequent
        requests with URIs in the same protection space.  It is recommended
        that this string be base64 or hexadecimal data.''')
    algorithm = auth_property('algorithm', doc='''
        A string indicating a pair of algorithms used to produce the digest
        and a checksum.  If this is not present it is assumed to be "MD5".
        If the algorithm is not understood, the challenge should be ignored
        (and a different one used, if there is more than one).''')
    qop = _set_property('qop', doc='''
        A set of quality-of-privacy modifies such as auth and auth-int.''')

    def _get_stale(self):
        val = self.get('stale')
        if val is not None:
            return val.lower() == 'true'
    def _set_stale(self, value):
        if value is None:
            self.pop('stale', None)
        else:
            self['stale'] = value and 'TRUE' or 'FALSE'
    stale = property(_get_stale, _set_stale, doc='''
        A flag, indicating that the previous request from the client was
        rejected because the nonce value was stale.''')
    del _get_stale, _set_stale

    # make auth_property a staticmethod so that subclasses of
    # `WWWAuthenticate` can use it for new properties.
    auth_property = staticmethod(auth_property)
    del _set_property


def quote_header_value(value, extra_chars='', allow_token=True):
    """Quote a header value if necessary."""
    value = str(value)
    if allow_token:
        token_chars = _token_chars | set(extra_chars)
        if set(value).issubset(token_chars):
            return value
    return '"%s"' % value.replace('\\', '\\\\').replace('"', '\\"')


def dump_header(iterable, allow_token=True):
    """Dump an HTTP header again.  This is the reversal of
    `parse_list_header`, `parse_set_header` and `parse_dict_header`.  This
    also quotes strings that include an equals sign unless you pass it as dict
    of key, value pairs.

    The `allow_token` parameter can be set to `False` to disallow tokens as
    values.  If this is enabled all values are quoted.
    """
    if isinstance(iterable, dict):
        items = []
        for key, value in iterable.iteritems():
            if value is None:
                items.append(key)
            else:
                items.append('%s=%s' % (
                    key,
                    quote_header_value(value, allow_token=allow_token)
                ))
    else:
        items = [quote_header_value(x, allow_token=allow_token)
                 for x in iterable]
    return ', '.join(items)


def parse_list_header(value):
    """Parse lists as described by RFC 2068 Section 2.

    In particular, parse comma-separated lists where the elements of
    the list may include quoted-strings.  A quoted-string could
    contain a comma.  A non-quoted string could have quotes in the
    middle.  Quotes are removed automatically after parsing.
    """
    result = []
    for item in _parse_list_header(value):
        if item[:1] == item[-1:] == '"':
            item = item[1:-1]
        result.append(item)
    return result


def parse_dict_header(value):
    """Parse lists of key, value paits as described by RFC 2068 Section 2 and
    convert them into a python dict.  If there is no value for a key it will
    be `None`.
    """
    result = {}
    for item in _parse_list_header(value):
        if '=' not in item:
            result[item] = None
            continue
        name, value = item.split('=', 1)
        if value[:1] == value[-1:] == '"':
            value = value[1:-1]
        result[name] = value
    return result


def parse_accept_header(value):
    """Parses an HTTP Accept-* header.  This does not implement a complete
    valid algorithm but one that supports at least value and quality
    extraction.

    Returns a new `Accept` object (basicly a list of ``(value, quality)``
    tuples sorted by the quality with some additional accessor methods).
    """
    if not value:
        return Accept(None)
    result = []
    for match in _accept_re.finditer(value):
        quality = match.group(2)
        if not quality:
            quality = 1
        else:
            quality = max(min(float(quality), 1), 0)
        result.append((match.group(1), quality))
    return Accept(result)


def parse_cache_control_header(value, on_update=None):
    """Parse a cache control header.  The RFC differs between response and
    request cache control, this method does not.  It's your responsibility
    to not use the wrong control statements.
    """
    if not value:
        return CacheControl(None, on_update)
    return CacheControl(parse_dict_header(value), on_update)


def parse_set_header(value, on_update=None):
    """Parse a set like header and return a `HeaderSet` object.  The return
    value is an object that treats the items case insensitive and keeps the
    order of the items.
    """
    if not value:
        return HeaderSet(None, on_update)
    return HeaderSet(parse_list_header(value), on_update)


def parse_authorization_header(value):
    """Parse an HTTP basic/digest authorization header transmitted by the web
    browser.  The return value is either `None` if the header was invalid or
    not given, otherwise an `Authorization` object.
    """
    if not value:
        return
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except ValueError:
        return
    if auth_type == 'basic':
        try:
            username, password = auth_info.decode('base64').split(':', 1)
        except Exception, e:
            return
        return Authorization('basic', {'username': username,
                                       'password': password})
    elif auth_type == 'digest':
        auth_map = parse_dict_header(auth_info)
        for key in 'username', 'realm', 'nonce', 'uri', 'nc', 'cnonce', \
                   'response':
            if not key in auth_map:
                return
        return Authorization('digest', auth_map)


def parse_www_authenticate_header(value, on_update=None):
    """Parse an HTTP WWW-Authenticate header into a `WWWAuthenticate`
    object."""
    if not value:
        return WWWAuthenticate(on_update=on_update)
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except (ValueError, AttributeError):
        return WWWAuthenticate(value.lower(), on_update=on_update)
    return WWWAuthenticate(auth_type, parse_dict_header(auth_info),
                           on_update)


def quote_etag(etag, weak=False):
    """Quote an etag."""
    if '"' in etag:
        raise ValueError('invalid etag')
    etag = '"%s"' % etag
    if weak:
        etag = 'w/' + etag
    return etag


def unquote_etag(etag):
    """Unquote a single etag.  Return a ``(etag, weak)`` tuple."""
    if not etag:
        return None, None
    etag = etag.strip()
    weak = False
    if etag[:2] in ('w/', 'W/'):
        weak = True
        etag = etag[2:]
    if etag[:1] == etag[-1:] == '"':
        etag = etag[1:-1]
    return etag, weak


def parse_etags(value):
    """Parse and etag header.  Returns an `ETags` object."""
    if not value:
        return ETags()
    strong = []
    weak = []
    end = len(value)
    pos = 0
    while pos < end:
        match = _etag_re.match(value, pos)
        if match is None:
            break
        is_weak, quoted, raw = match.groups()
        if raw == '*':
            return ETags(star_tag=True)
        elif quoted:
            raw = quoted
        if is_weak:
            weak.append(raw)
        else:
            strong.append(raw)
        pos = match.end()
    return ETags(strong, weak)


def generate_etag(data):
    """Generate an etag for some data."""
    return md5(data).hexdigest()


def parse_date(value):
    """Parse one of the following date formats into a datetime object:

    .. sourcecode:: text

        Sun, 06 Nov 1994 08:49:37 GMT  ; RFC 822, updated by RFC 1123
        Sunday, 06-Nov-94 08:49:37 GMT ; RFC 850, obsoleted by RFC 1036
        Sun Nov  6 08:49:37 1994       ; ANSI C's asctime() format

    If parsing fails the return value is `None`.
    """
    if value:
        t = rfc822.parsedate_tz(value.strip())
        if t is not None:
            # if no timezone is part of the string we assume UTC
            if t[-1] is None:
                t = t[:-1] + (0,)
            return datetime.utcfromtimestamp(rfc822.mktime_tz(t))


def is_resource_modified(environ, etag=None, data=None, last_modified=None):
    """Convenience method for conditional requests."""
    if etag is None and data is not None:
        etag = generate_etag(data)
    elif data is not None:
        raise TypeError('both data and etag given')
    if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
        return False

    unmodified = False
    if isinstance(last_modified, basestring):
        last_modified = parse_date(last_modified)
    modified_since = parse_date(environ.get('HTTP_IF_MODIFIED_SINCE'))

    if modified_since and last_modified and last_modified <= modified_since:
        unmodified = True
    if etag:
        if_none_match = parse_etags(environ.get('HTTP_IF_NONE_MATCH'))
        if if_none_match:
            unmodified = if_none_match.contains_raw(etag)

    return not unmodified
