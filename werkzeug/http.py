# -*- coding: utf-8 -*-
"""
    werkzeug.http
    ~~~~~~~~~~~~~

    Various WSGI related helper functions and classes.


    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
try:
    set = set
except NameError:
    from sets import Set as set
import re


_accept_re = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')
_token_chars = set("!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   '^_`abcdefghijklmnopqrstuvwxyz|~')
_token = '[%s]' % ''.join(_token_chars).replace('-', '\\-')
_cachecontrol_re = re.compile(r'(%s+)(?:=(?:(%s+|".*?")))?' % (_token, _token))


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
    Subclass of a list for easier access to the accept values.  Sorted
    by quality, best first.
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
        """Get the position of en entry or raise IndexError."""
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
        """Just the values, not the qualities."""
        return [x[1] for x in self]

    def itervalues(self):
        """Iterate over all values."""
        for item in self:
            yield item[0]

    def best(self):
        """The best match as value."""
        return self and self[0][0] or None
    best = property(best)


class CacheControl(dict):
    """
    Wrapper around a dict for cache control headers.
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

    # make cache property a staticmethod so that subclasses of
    # `CacheControl` can use it for new properties.
    cache_property = staticmethod(cache_property)
    del calls_update


def parse_accept_header(value):
    """
    Parses an HTTP Accept-* header.  This does not implement a complete valid
    algorithm but one that supports at least value and quality extraction.

    Returns a new `Accept` object (basicly a list of ``(value, quality)``
    tuples sorted by the quality with some additional accessor methods)
    """
    result = []
    for match in _accept_re.finditer(value):
        quality = match.group(2)
        if not quality:
            quality = 1
        else:
            quality = max(min(float(quality), 1), 0)
        result.append((match.group(1), quality))
    return Accept(result)


def parse_cache_control_header(value):
    """
    Parse a cache control header.  The RFC differs between response and
    request cache control, this method does not.  It's your responsibility
    to not use the wrong control statements.
    """
    result = {}
    for match in _cachecontrol_re.finditer(value):
        name, value = match.group(1, 2)
        if value and value[0] == value[-1] == '"':
            value = value[1:-1]
        result[name] = value
    return CacheControl(result)
