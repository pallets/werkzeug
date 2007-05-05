# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    Various utils.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
from cStringIO import StringIO
try:
    set
except NameError:
    from sets import Set as set


class MultiDict(dict):
    """
    A dict that takes a list of multiple values as only argument
    in order to store multiple values per key.
    """

    def __init__(self, mapping=()):
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

    def iteritems(self):
        for key, values in dict.iteritems(self):
            yield key, values[0]

    iterlists = dict.iteritems

    def itervalues(self):
        for values in dict.itervalues(self):
            yield values[0]

    def copy(self):
        """Return a shallow copy of this object."""
        md = MultiDict()
        for key, values in dict.iteritems(self):
            md.setlist(key, values)
        return md

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
        # this repr is not evallable...
        return '%s(%s)' % (self.__class__.__name__, dict.__repr__(self)[1:-1])


class CombinedMultiDict(MultiDict):
    """
    Pass it multiple multidicts to create a new read only
    dict which resolves items from the passed dicts.
    """

    def __init__(self, dicts=None):
        self.dicts = dicts or []

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
        rv = []
        for i in self.keys():
            rv.append(self[i])
        return rv

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

    def iterkeys(self):
        return iter(self.keys())

    __iter__ = iterkeys

    def itervalues(self):
        return iter(self.values())

    def iteritems(self):
        return iter(self.items())

    def iterlists(self):
        return iter(self.lists())

    def copy(self):
        """Return a shallow copy of this object."""
        return self.__class__(self.dicts[:])

    def __immutable(self, *args):
        raise TypeError('%r instances are immutable' %
                        self.__class__.__name__)

    setlist = setdefault = setlistdefault = update = pop = popitem = \
    poplist = popitemlist = __setitem__ = __delitem__ = __immutable

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def __repr__(self):
        return '%s(...)' % self.__class__.__name__


class FieldStorage(object):
    """
    Represents an uploaded file.
    """

    def __init__(self, name, filename, ftype, data):
        self.name = name
        self.type = ftype
        self.filename = filename
        self.data = data

    def read(self, *args):
        if not hasattr(self, '_cached_buffer'):
            self._cached_buffer = StringIO(self.data)
        return self._cached_buffer.read(*args)

    def readline(self, *args):
        if not hasattr(self, '_cached_buffer'):
            self._cached_buffer = StringIO(self.data)
        return self._cached_buffer.readline(*args)

    def readlines(self):
        if not hasattr(self, '_cached_buffer'):
            self._cached_buffer = StringIO(self.data)
        return self._cached_buffer.readlines()

    def __iter__(self):
        while True:
            row = self.readline()
            if not row:
                break
            yield row

    def __repr__(self):
        return '<%s: %r (%r)>' % (
            self.__class__.__name__,
            self.filename,
            self.type
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

    def __delitem__(self, key):
        key = key.lower()
        new = []
        for k, v in self._list:
            if k != key:
                new.append((k, v))
        self._list[:] = new

    def __contains__(self, key):
        key = key.lower()
        for k, v in self._list:
            if k.lower() == key:
                return True
        return False

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
