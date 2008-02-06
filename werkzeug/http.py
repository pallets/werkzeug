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


_accept_re = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')
_token_chars = set("!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   '^_`abcdefghijklmnopqrstuvwxyz|~')
_token = '[%s]' % ''.join(_token_chars).replace('-', '\\-')
_cachecontrol_re = re.compile(r'(%s+)(?:=(?:(%s+|".*?")))?' %
                              (_token, _token))
_etag_re = re.compile(r'([Ww]/)?(?:"(.*?)"|(.*?))(?:\s*,\s*|$)')


HTTP_STATUS_CODES = {
    100:    'Continue',
    101:    'Switching Protocols',
    102:    'Processing',
    200:    'OK',
    201:    'Created',
    202:    'Accepted',
    203:    'Non Authoritative Information',
    204:    'No Content',
    205:    'Reset Content',
    206:    'Partial Content',
    207:    'Multi Status',
    300:    'Multiple Choices',
    301:    'Moved Permanently',
    302:    'Found',
    303:    'See Other',
    304:    'Not Modified',
    305:    'Use Proxy',
    307:    'Temporary Redirect',
    400:    'Bad Request',
    401:    'Unauthorized',
    402:    'Payment Required', # unused
    403:    'Forbidden',
    404:    'Not Found',
    405:    'Method Not Allowed',
    406:    'Not Acceptable',
    407:    'Proxy Authentication Required',
    408:    'Request Timeout',
    409:    'Conflict',
    410:    'Gone',
    411:    'Length Required',
    412:    'Precondition Failed',
    413:    'Request Entity Too Large',
    414:    'Request URI Too Long',
    415:    'Unsupported Media Type',
    416:    'Requested Range Not Satisfiable',
    417:    'Expectation Failed',
    422:    'Unprocessable Entity',
    423:    'Locked',
    424:    'Failed Dependency',
    426:    'Upgrade Required',
    449:    'Retry With', # propritary MS extension
    500:    'Internal Server Error',
    501:    'Not Implemented',
    502:    'Bad Gateway',
    503:    'Service Unavailable',
    504:    'Gateway Timeout',
    505:    'HTTP Version Not Supported',
    507:    'Insufficient Storage',
    510:    'Not Extended'
}


class Accept(list):
    """
    An `Accept` object is just a list subclass for lists of
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
        """
        Beside index lookup (getting item n) you can also pass it a string to
        get the quality for the item.  If the item is not in the list, the
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
        return [x[1] for x in self]

    def itervalues(self):
        """Iterate over all values."""
        for item in self:
            yield item[0]

    def best(self):
        """The best match as value."""
        return self and self[0][0] or None
    best = property(best)


class HeaderSet(object):
    """
    Similar to the `ETags` class this implements a set like structure.
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
        """
        Remove a layer from the set.  This raises an `IndexError` if the
        header is not in the set.
        """
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
        """
        Return the set as real python set structure.  When calling this all
        the items are converted to lowercase and the ordering is lost.
        """
        if preserve_casing:
            return set(self._headers)
        return set(self._set)

    def to_header(self):
        """Convert the header set into an HTTP header string."""
        return ', '.join(self._headers)

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


class CacheControl(dict):
    """
    Subclass of a dict that stores values for a Cache-Control header.  It has
    accesors for all the cache-control directives specified in RFC 2616.  The
    class does not differentiate between request and response directives.

    Because the cache-control directives in the HTTP header use dashes the
    python descriptors use underscores for that.

    To get a header of the `CacheControl` object again you can convert the
    object into a string or call the `to_header()` function.  If you plan
    to subclass it and add your own items have a look at the sourcecode for
    that class.

    The following attributes are exposed:

    `no_cache`, `no_store`, `max_age`, `max_stale`, `min_fresh`,
    `no_transform`, `only_if_cached`, `public`, `private`, `must_revalidate`,
    `proxy_revalidate`, and `s_maxage`
    """

    def cache_property(key, default, type):
        """
        Return a new property object for a cache header.  Useful if you
        want to add support for a cache extension in a subclass.
        """
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
        self.on_update = on_update
        if values is None:
            dict.__init__(self)
            self.provided = False
        else:
            dict.__init__(self, values)
            self.provided = True

    def calls_update(f):
        def oncall(self, *args, **kw):
            rv = f(self, *args, **kw)
            if self.on_update is not None:
                self.on_update(self)
            return rv
        try:
            oncall.__name__ = f.__name__
            oncall.__module__ = f.__module__
            oncall.__doc__ = f.__doc__
        except:
            pass
        return oncall

    __setitem__ = calls_update(dict.__setitem__)
    __delitem__ = calls_update(dict.__delitem__)
    clear = calls_update(dict.clear)
    pop = calls_update(dict.pop)
    popitem = calls_update(dict.popitem)
    setdefault = calls_update(dict.setdefault)
    update = calls_update(dict.update)

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
    _set_cache_value = calls_update(_set_cache_value)

    def to_header(self):
        """Convert the stored values into a cache control header."""
        items = []
        for key, value in self.iteritems():
            if value is None:
                items.append(key)
            else:
                value = str(value)
                if not set(value).issubset(_token_chars):
                    value = '"%s"' % value.replace('"', "'")
                items.append('%s=%s' % (key, value))
        return ', '.join(items)

    def __str__(self):
        return self.to_header()

    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__,
            dict.__repr__(self)
        )

    # make cache_property a staticmethod so that subclasses of
    # `CacheControl` can use it for new properties.
    cache_property = staticmethod(cache_property)
    del calls_update


class ETags(object):
    """
    A set that can be used to check if one etag is present in a collection
    of etags.
    """

    def __init__(self, strong_etags=None, weak_etags=None, star_tag=False):
        self._strong = frozenset(not star_tag and strong_etags or ())
        self._weak = frozenset(weak_etags or ())
        self.star_tag = star_tag

    def as_set(self, include_weak=False):
        """
        Convert the `ETags` object into a python set.  Per default all the
        weak etags are not part of this set.
        """
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
        """
        When passed a quoted tag it will check if this tag is part of the set.
        If the tag is weak it is checked against weak and strong tags, otherwise
        weak only.
        """
        etag, weak = unquote_etag(etag)
        if weak:
            return self.contains_weak(etag)
        return self.contains(etag)

    def to_header(self):
        """Convert the etags set into a HTTP header string."""
        if self.star_tag:
            return '*'
        return ', '.join(['"%s"' % item for item in self.as_set(True)])

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


def parse_accept_header(value):
    """
    Parses an HTTP Accept-* header.  This does not implement a complete valid
    algorithm but one that supports at least value and quality extraction.

    Returns a new `Accept` object (basicly a list of ``(value, quality)``
    tuples sorted by the quality with some additional accessor methods)
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
    """
    Parse a cache control header.  The RFC differs between response and
    request cache control, this method does not.  It's your responsibility
    to not use the wrong control statements.
    """
    if not value:
        return CacheControl(None, on_update)
    result = {}
    for match in _cachecontrol_re.finditer(value):
        name, value = match.group(1, 2)
        if value and value[0] == value[-1] == '"':
            value = value[1:-1]
        result[name] = value
    return CacheControl(result, on_update)


def parse_set_header(value, on_update=None):
    """
    Parse a set like header and return a `HeaderSet` object.  The return
    value is an object that treats the items case insensitive and keeps the
    order of the items.
    """
    if not value:
        return HeaderSet(None, on_update)
    return HeaderSet([x.strip() for x in value.split(',')], on_update)


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
    """
    Parse one of the following date formats into a datetime object:

    .. sourcecode:: text

        Sun, 06 Nov 1994 08:49:37 GMT  ; RFC 822, updated by RFC 1123
        Sunday, 06-Nov-94 08:49:37 GMT ; RFC 850, obsoleted by RFC 1036
        Sun Nov  6 08:49:37 1994       ; ANSI C's asctime() format

    If parsing fails the return value is `None`.
    """
    if value:
        t = rfc822.parsedate_tz(value)
        if t is not None:
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
