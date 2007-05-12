# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    Various utils.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import os
import cgi
import urllib
from cStringIO import StringIO
try:
    set
except NameError:
    from sets import Set as set

    def reversed(item):
        return tuple(item)[::-1]


class MultiDict(dict):
    """
    A dict that takes a list of multiple values as only argument
    in order to store multiple values per key.
    """

    def __init__(self, mapping=()):
        if isinstance(mapping, MultiDict):
            dict.__init__(self, mapping.lists())
        elif isinstance(mapping, dict):
            tmp = {}
            for key, value in mapping:
                tmp[key] = [value]
            dict.__init__(self, tmp)
        else:
            tmp = {}
            for key, value in mapping:
                tmp.setdefault(key, []).append(value)
            dict.__init__(self, tmp)

    def __getitem__(self, key):
        """
        Return the first data value for this key;
        raises KeyError if not found.
        """
        return dict.__getitem__(self, key)[0]

    def __setitem__(self, key, value):
        """Set an item as list."""
        dict.__setitem__(self, key, [value])

    def get(self, key, default=None):
        """Return the default value if the requested data doesn't exist"""
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key):
        """Return an empty list if the requested data doesn't exist"""
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return []

    def setlist(self, key, new_list):
        """Set new values for an key."""
        dict.__setitem__(self, key, list(new_list))

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        else:
            default = self[key]
        return default

    def setlistdefault(self, key, default_list=()):
        if key not in self:
            default_list = list(default_list)
            dict.__setitem__(self, key, default_list)
        else:
            default_list = self.getlist(key)
        return default_list

    def items(self):
        """
        Return a list of (key, value) pairs, where value is the last item in
        the list associated with the key.
        """
        return [(key, self[key]) for key in self.iterkeys()]

    lists = dict.items

    def values(self):
        """Returns a list of the last value on every key list."""
        return [self[key] for key in self.iterkeys()]

    listvalues = dict.values

    def iteritems(self):
        for key, values in dict.iteritems(self):
            yield key, values[0]

    iterlists = dict.iteritems

    def itervalues(self):
        for values in dict.itervalues(self):
            yield values[0]

    iterlistvalues = dict.itervalues

    def copy(self):
        """Return a shallow copy of this object."""
        return self.__class__(self)

    def update(self, other_dict):
        """update() extends rather than replaces existing key lists."""
        if isinstance(other_dict, MultiDict):
            for key, value_list in other_dict.iterlists():
                self.setlistdefault(key, []).extend(value_list)
        elif isinstance(other_dict, dict):
            for key, value in other_dict.items():
                self.setlistdefault(key, []).append(value)
        else:
            for key, value in other_dict:
                self.setlistdefault(key, []).append(value)

    def pop(self, *args):
        """Pop the first item for a list on the dict."""
        return dict.pop(self, *args)[0]

    def popitem(self):
        """Pop an item from the dict."""
        item = dict.popitem(self)
        return (item[0], item[1][0])

    poplist = dict.pop
    popitemlist = dict.popitem

    def __repr__(self):
        tmp = []
        for key, values in self.iterlists():
            for value in values:
                tmp.append((key, value))
        return '%s(%r)' % (self.__class__.__name__, tmp)


class CombinedMultiDict(MultiDict):
    """
    Pass it multiple multidicts to create a new read only
    dict which resolves items from the passed dicts.
    """

    def __init__(self, dicts=None):
        self.dicts = dicts or []

    def fromkeys(cls):
        raise TypeError('cannot create %r instances by fromkeys' %
                        cls.__name__)
    fromkeys = classmethod(fromkeys)

    def __getitem__(self, key):
        for d in self.dicts:
            if key in d:
                return d[key]
        raise KeyError(key)

    def get(self, key, default=None):
        for d in self.dicts:
            if key in d:
                return d[key]
        return default

    def getlist(self, key):
        rv = []
        for d in self.dicts:
            rv.extend(d.getlist(key))
        return rv

    def keys(self):
        rv = set()
        for d in self.dicts:
            rv.update(d.keys())
        return list(rv)

    def values(self):
        rv = {}
        for d in reversed(self.dicts):
            rv.update(d)
        return rv.values()

    def items(self):
        rv = {}
        for d in reversed(self.dicts):
            rv.update(d)
        return rv.items()

    def lists(self):
        rv = {}
        for d in self.dicts:
            for k, v in d.iterlists():
                rv.setdefault(k, []).extend(v)
        return rv.items()

    def listvalues(self):
        rv = {}
        for d in reversed(self.dicts):
            rv.update(d.lists())
        return rv.values()

    def iterkeys(self):
        return iter(self.keys())

    __iter__ = iterkeys

    def itervalues(self):
        return iter(self.values())

    def iteritems(self):
        return iter(self.items())

    def iterlists(self):
        return iter(self.lists())

    def iterlistvalues(self):
        return iter(self.listvalues())

    def copy(self):
        """Return a shallow copy of this object."""
        return self.__class__(self.dicts[:])

    def _immutable(self, *args):
        raise TypeError('%r instances are immutable' %
                        self.__class__.__name__)

    setlist = setdefault = setlistdefault = update = pop = popitem = \
    poplist = popitemlist = __setitem__ = __delitem__ = _immutable
    del _immutable

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        for d in self.dicts:
            if key in d:
                return True
        return False

    has_key = __contains__

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.dicts)


class FileStorage(object):
    """
    Represents an uploaded file.
    """

    def __init__(self, name, filename, content_type, content_length, stream):
        self.name = name
        self.filename = filename
        self.content_type = content_type
        self.content_length = content_length
        self.stream = stream

        self.read = stream.read
        self.readline = stream.readline
        self.readlines = stream.readlines

    def __len__(self):
        return self.content_length

    def __iter__(self):
        return iter(self.readline, '')

    def __repr__(self):
        return '<%s: %r (%r)>' % (
            self.__class__.__name__,
            self.filename,
            self.content_type
        )


class Headers(object):
    """
    An object that stores some headers.
    """

    def __init__(self, defaults=None):
        self._list = []
        if isinstance(defaults, dict):
            for key, value in defaults.iteritems():
                if isinstance(value, (tuple, list)):
                    for v in value:
                        self._list.append((key, v))
                else:
                    self._list.append((key, value))
        elif defaults is not None:
            for key, value in defaults:
                self._list.append((key, value))

    def __getitem__(self, key):
        ikey = key.lower()
        for k, v in self._list:
            if k.lower() == ikey:
                return v
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key):
        ikey = key.lower()
        result = []
        for k, v in self._list:
            if k.lower() == ikey:
                result.append((k, v))
        return result

    def setlist(self, key, values):
        del self[key]
        self.addlist(key, values)

    def addlist(self, key, values):
        self._list.extend(values)

    def lists(self, lowercased=False):
        if not lowercased:
            return self._list[:]
        return [(x.lower(), y) for x, y in self._list]

    def iterlists(self, lowercased=False):
        for key, value in self._list:
            if lowercased:
                key = key.lower()
            yield key, value

    def iterkeys(self):
        for key, _ in self.iterlists():
            yield key

    def itervalues(self):
        for _, value in self.iterlists():
            yield value

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def __delitem__(self, key):
        key = key.lower()
        new = []
        for k, v in self._list:
            if k != key:
                new.append((k, v))
        self._list[:] = new

    remove = __delitem__

    def __contains__(self, key):
        key = key.lower()
        for k, v in self._list:
            if k.lower() == key:
                return True
        return False

    has_key = __contains__

    def __iter__(self):
        return iter(self._list)

    def add(self, key, value):
        """add a new header tuple to the list"""
        self._list.append((key, value))

    def clear(self):
        """clears all headers"""
        del self._list[:]

    def set(self, key, value):
        """remove all header tuples for key and add
        a new one
        """
        del self[key]
        self.add(key, value)

    __setitem__ = set

    def to_list(self, charset):
        """Create a str only list of the headers."""
        result = []
        for k, v in self:
            if isinstance(v, unicode):
                v = v.encode(charset)
            else:
                v = str(v)
            result.append((k, v))
        return result

    def copy(self):
        return self.__class__(self._list)

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self._list
        )


class SharedDataMiddleware(object):
    """
    Redirects calls to an folder with static data.
    """

    def __init__(self, app, exports):
        self.app = app
        self.exports = exports

    def serve_file(self, filename, start_response):
        from mimetypes import guess_type
        guessed_type = guess_type(filename)
        if guessed_type[0] is None:
            mime_type = 'text/plain'
        else:
            mime_type = guessed_type[0]
        start_response('200 OK', [('Content-Type', mime_type)])
        fp = file(filename, 'rb')
        try:
            result = fp.read()
        finally:
            fp.close()
        return iter([result])

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        for search_path, file_path in self.exports.iteritems():
            if not search_path.endswith('/'):
                search_path += '/'
            if path.startswith(search_path):
                real_path = os.path.join(file_path, path[len(search_path):])
                if os.path.exists(real_path) and os.path.isfile(real_path):
                    return self.serve_file(real_path, start_response)
        return self.app(environ, start_response)


class lazy_property(object):
    """
    Descriptor implementing a "lazy property", i.e. the function
    calculating the property value is called only once.
    """

    def __init__(self, func, name=None, doc=None):
        self._func = func
        self._name = name or func.func_name
        self.__doc__ = doc or func.__doc__

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        value = self._func(obj)
        setattr(obj, self._name, value)
        return value


def url_decode(s, charset='utf-8'):
    """
    Parse a querystring and return it as `MultiDict`.
    """
    tmp = []
    for key, values in cgi.parse_qs(str(s)):
        for value in values:
            tmp.append((key, value.decode(charset, 'ignore')))
    return MultiDict(tmp)


def url_encode(obj, charset='utf-8'):
    """
    Urlencode a dict/MultiDict.
    """
    if isinstance(obj, dict):
        items = [(key, [value]) for key, value in obj.iteritems()]
    else:
        items = obj.lists()
    tmp = []
    for key, values in items:
        for value in values:
            if isinstance(value, unicode):
                value = value.encode(charset)
            tmp.append('%s=%s' % (urllib.quote_plus(key),
                                  urllib.quote_plus(value)))
    return '&'.join(tmp)


def url_quote(s, charset='utf-8'):
    """
    URL encode a single string with a given encoding.
    """
    if isinstance(s, unicode):
        s = s.encode(charset)
    return urllib.quote_plus(s)


def url_unquote(s, charset='utf-8'):
    """
    URL decode a single string with a given decoding.
    """
    return urllib.unquote_plus(s).decode(charset, 'ignore')


escape = cgi.escape
