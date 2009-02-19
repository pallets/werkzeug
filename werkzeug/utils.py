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
from itertools import chain
from time import asctime, gmtime, time
from datetime import timedelta

from werkzeug._internal import _patch_wrapper, _decode_unicode, \
     _empty_stream, _iter_modules, _ExtendedCookie, _ExtendedMorsel, \
     _DictAccessorProperty, _dump_date, _parse_signature, _missing


_format_re = re.compile(r'\$(?:(%s)|\{(%s)\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))
_entity_re = re.compile(r'&([^;]+);')


class MultiDict(dict):
    """A :class:`MultiDict` is a dictionary subclass customized to deal with
    multiple values for the same key which is for example used by the parsing
    functions in the wrappers.  This is necessary because some HTML form
    elements pass multiple values for the same key.

    :class:`MultiDict` implements the all standard dictionary methods.
    Internally, it saves all values for a key as a list, but the standard dict
    access methods will only return the first value for a key. If you want to
    gain access to the other values too you have to use the `list` methods as
    explained below.

    Basic Usage:

    >>> d = MultiDict([('a', 'b'), ('a', 'c')])
    >>> d
    MultiDict([('a', 'b'), ('a', 'c')])
    >>> d['a']
    'b'
    >>> d.getlist('a')
    ['b', 'c']
    >>> 'a' in d
    True

    It behaves like a normal dict thus all dict functions will only return the
    first value when multiple values for one key are found.

    From Werkzeug 0.3 onwards, the `KeyError` raised by this class is also a
    subclass of the :exc:`~exceptions.BadRequest` HTTP exception and will
    render a page for a ``400 BAD REQUEST`` if catched in a catch-all for HTTP
    exceptions.

    A :class:`MultiDict` can be constructed from an iterable of
    ``(key, value)`` tuples, a dict, a :class:`MultiDict` or with Werkzeug 0.2
    onwards some keyword parameters.

    :param mapping: the initial value for the :class:`MultiDict`.  Either a
                    regular dict, an iterable of ``(key, value)`` tuples
                    or `None`.
    """

    # the key error this class raises.  Because of circular dependencies
    # with the http exception module this class is created at the end of
    # this module.
    KeyError = None

    def __init__(self, mapping=None):
        if isinstance(mapping, MultiDict):
            dict.__init__(self, [(k, v[:]) for k, v in mapping.lists()])
        elif isinstance(mapping, dict):
            tmp = {}
            for key, value in mapping.iteritems():
                if isinstance(value, (tuple, list)):
                    value = list(value)
                else:
                    value = [value]
                tmp[key] = value
            dict.__init__(self, tmp)
        else:
            tmp = {}
            for key, value in mapping or ():
                tmp.setdefault(key, []).append(value)
            dict.__init__(self, tmp)

    def __getitem__(self, key):
        """Return the first data value for this key;
        raises KeyError if not found.

        :param key: The key to be looked up.
        :raise KeyError: if the key does not exist.
        """
        if key in self:
            return dict.__getitem__(self, key)[0]
        raise self.KeyError(key)

    def __setitem__(self, key, value):
        """Set an item as list."""
        dict.__setitem__(self, key, [value])

    def get(self, key, default=None, type=None):
        """Return the default value if the requested data doesn't exist.
        If `type` is provided and is a callable it should convert the value,
        return it or raise a :exc:`ValueError` if that is not possible.  In
        this case the function will return the default as if the value was not
        found:

        >>> d = MultiDict(dict(foo='42', bar='blub'))
        >>> d.get('foo', type=int)
        42
        >>> d.get('bar', -1, type=int)
        -1

        :param key: The key to be looked up.
        :param default: The default value to be returned if the key can't
                        be looked up.  If not further specified `None` is
                        returned.
        :param type: A callable that is used to cast the value in the
                     :class:`MultiDict`.  If a :exc:`ValueError` is raised
                     by this callable the default value is returned.
        """
        try:
            rv = self[key]
            if type is not None:
                rv = type(rv)
        except (KeyError, ValueError):
            rv = default
        return rv

    def getlist(self, key, type=None):
        """Return the list of items for a given key. If that key is not in the
        `MultiDict`, the return value will be an empty list.  Just as `get`
        `getlist` accepts a `type` parameter.  All items will be converted
        with the callable defined there.

        :param key: The key to be looked up.
        :param type: A callable that is used to cast the value in the
                     :class:`MultiDict`.  If a :exc:`ValueError` is raised
                     by this callable the value will be removed from the list.
        :return: a :class:`list` of all the values for the key.
        """
        try:
            rv = dict.__getitem__(self, key)
        except KeyError:
            return []
        if type is None:
            return rv
        result = []
        for item in rv:
            try:
                result.append(type(item))
            except ValueError:
                pass
        return result

    def setlist(self, key, new_list):
        """Remove the old values for a key and add new ones.  Note that the list
        you pass the values in will be shallow-copied before it is inserted in
        the dictionary.

        >>> d = MultiDict()
        >>> d.setlist('foo', ['1', '2'])
        >>> d['foo']
        '1'
        >>> d.getlist('foo')
        ['1', '2']

        :param key: The key for which the values are set.
        :param new_list: An iterable with the new values for the key.  Old values
                         are removed first.
        """
        dict.__setitem__(self, key, list(new_list))

    def setdefault(self, key, default=None):
        """Returns the value for the key if it is in the dict, otherwise it
        returns `default` and sets that value for `key`.

        :param key: The key to be looked up.
        :param default: The default value to be returned if the key is not
                        in the dict.  If not further specified it's `None`.
        """
        if key not in self:
            self[key] = default
        else:
            default = self[key]
        return default

    def setlistdefault(self, key, default_list=()):
        """Like `setdefault` but sets multiple values.

        :param key: The key to be looked up.
        :param default: An iterable of default values.  It is either copied
                        (in case it was a list) or converted into a list
                        before returned.
        :return: a :class:`list`
        """
        if key not in self:
            default_list = list(default_list)
            dict.__setitem__(self, key, default_list)
        else:
            default_list = self.getlist(key)
        return default_list

    def items(self):
        """Return a list of ``(key, value)`` pairs, where value is the first
        item in the list associated with the key.

        :return: a :class:`list`
        """
        return [(key, self[key]) for key in self.iterkeys()]

    #: Return a list of ``(key, value)`` pairs, where values is the list of
    #: all values assoiciated with the key.
    #:
    #: :return: a :class:`list`
    lists = dict.items

    def values(self):
        """Returns a list of the last value on every key list.

        :return: a :class:`list`.
        """
        return [self[key] for key in self.iterkeys()]

    #: Return a list of all values assoiciated with a key.  Zipping
    #: :meth:`keys` and this is the same as calling :meth:`lists`:
    #:
    #: >>> d = MultiDict({"foo": [1, 2, 3]})
    #: >>> zip(d.keys(), d.listvalues()) == d.lists()
    #: True
    #:
    #: :return: a :class:`list`
    listvalues = dict.values

    def iteritems(self):
        """Like :meth:`items` but returns an iterator."""
        for key, values in dict.iteritems(self):
            yield key, values[0]

    #: Return a list of all values assoiciated with a key.
    #:
    #: :return: a :class:`list`
    iterlists = dict.iteritems

    def itervalues(self):
        """Like :meth:`values` but returns an iterator."""
        for values in dict.itervalues(self):
            yield values[0]

    #: like :meth:`listvalues` but returns an iterator.
    iterlistvalues = dict.itervalues

    def copy(self):
        """Return a shallow copy of this object."""
        return self.__class__(self)

    def to_dict(self, flat=True):
        """Return the contents as regular dict.  If `flat` is `True` the
        returned dict will only have the first item present, if `flat` is
        `False` all values will be returned as lists.

        :param flat: If set to `False` the dict returned will have lists
                     with all the values in it.  Otherwise it will only
                     contain the first item for each key.
        :return: a :class:`dict`
        """
        if flat:
            return dict(self.iteritems())
        return dict(self)

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

    def pop(self, key, default=_missing):
        """Pop the first item for a list on the dict.  Afterwards the
        key is removed from the dict, so additional values are discarded:

        >>> d = MultiDict({"foo": [1, 2, 3]})
        >>> d.pop("foo")
        1
        >>> "foo" in d
        False

        :param key: the key to pop.
        :param default: if provided the value to return if the key was
                        not in the dictionary.
        """
        if default is not _missing:
            return dict.pop(self, key, default)
        try:
            return dict.pop(self, key)[0]
        except KeyError, e:
            raise self.KeyError(str(e))

    def popitem(self):
        """Pop an item from the dict."""
        try:
            item = dict.popitem(self)
            return (item[0], item[1][0])
        except KeyError, e:
            raise self.KeyError(str(e))

    def poplist(self, key):
        """Pop the list for a key from the dict.  If the key is not in the dict
        an empty list is returned.

        .. versionchanged:: 0.5
           If the key does no longer exist a list is returned instead of
           raising an error.
        """
        return dict.pop(self, key, [])

    def popitemlist(self):
        """Pop a ``(key, list)`` tuple from the dict."""
        try:
            return dict.popitem(self)
        except KeyError, e:
            raise self.KeyError(str(e))

    def __repr__(self):
        tmp = []
        for key, values in self.iterlists():
            for value in values:
                tmp.append((key, value))
        return '%s(%r)' % (self.__class__.__name__, tmp)


class CombinedMultiDict(MultiDict):
    """A read only :class:`MultiDict` that you can pass multiple :class:`MultiDict`
    instances as sequence and it will combine the return values of all wrapped
    dicts:

    >>> from werkzeug import MultiDict, CombinedMultiDict
    >>> post = MultiDict([('foo', 'bar')])
    >>> get = MultiDict([('blub', 'blah')])
    >>> combined = CombinedMultiDict([get, post])
    >>> combined['foo']
    'bar'
    >>> combined['blub']
    'blah'

    This works for all read operations and will raise a `TypeError` for
    methods that usually change data which isn't possible.

    From Werkzeug 0.3 onwards, the `KeyError` raised by this class is also a
    subclass of the :exc:`~exceptions.BadRequest` HTTP exception and will
    render a page for a ``400 BAD REQUEST`` if catched in a catch-all for HTTP
    exceptions.
    """

    def __init__(self, dicts=None):
        self.dicts = dicts or []

    @classmethod
    def fromkeys(cls):
        raise TypeError('cannot create %r instances by fromkeys' %
                        cls.__name__)

    def __getitem__(self, key):
        for d in self.dicts:
            if key in d:
                return d[key]
        raise self.KeyError(key)

    def get(self, key, default=None, type=None):
        for d in self.dicts:
            if key in d:
                if type is not None:
                    try:
                        return type(d[key])
                    except ValueError:
                        continue
                return d[key]
        return default

    def getlist(self, key, type=None):
        rv = []
        for d in self.dicts:
            rv.extend(d.getlist(key, type))
        return rv

    def keys(self):
        rv = set()
        for d in self.dicts:
            rv.update(d.keys())
        return list(rv)

    def iteritems(self):
        found = set()
        for d in self.dicts:
            for key, value in d.iteritems():
                if not key in found:
                    found.add(key)
                    yield key, value

    def itervalues(self):
        for key, value in self.iteritems():
            yield value

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())

    def lists(self):
        rv = {}
        for d in self.dicts:
            rv.update(d)
        return rv.items()

    def listvalues(self):
        rv = {}
        for d in reversed(self.dicts):
            rv.update(d)
        return rv.values()

    def iterkeys(self):
        return iter(self.keys())

    __iter__ = iterkeys

    def iterlists(self):
        return iter(self.lists())

    def iterlistvalues(self):
        return iter(self.listvalues())

    def copy(self):
        """Return a shallow copy of this object."""
        return self.__class__(self.dicts[:])

    def to_dict(self, flat=True):
        """Return the contents as regular dict.  If `flat` is `True` the
        returned dict will only have the first item present, if `flat` is
        `False` all values will be returned as lists.

        :param flat: If set to `False` the dict returned will have lists
                     with all the values in it.  Otherwise it will only
                     contain the first item for each key.
        :return: a :class:`dict`
        """
        rv = {}
        for d in reversed(self.dicts):
            rv.update(d.to_dict(flat))
        return rv

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
    """The :class:`FileStorage` class is a thin wrapper over incoming files.
    It is used by the request object to represent uploaded files.  All the
    attributes of the wrapper stream are proxied by the file storage so
    it's possible to do ``storage.read()`` instead of the long form
    ``storage.stream.read()``.
    """

    def __init__(self, stream=None, filename=None, name=None,
                 content_type='application/octet-stream', content_length=-1):
        self.name = name
        self.stream = stream or _empty_stream
        self.filename = filename or getattr(stream, 'name', None)
        self.content_type = content_type
        self.content_length = content_length

    def save(self, dst, buffer_size=16384):
        """Save the file to a destination path or file object.  If the
        destination is a file object you have to close it yourself after the
        call.  The buffer size is the number of bytes held in the memory
        during the copy process.  It defaults to 16KB.

        :param dst: a filename or open file object the uploaded file
                    is saved in.
        :param buffer_size: the size of the buffer.  This works the same as
                            the `length` parameter of
                            :func:`shutil.copyfileobj`.
        """
        from shutil import copyfileobj
        close_dst = False
        if isinstance(dst, basestring):
            dst = file(dst, 'wb')
            close_dst = True
        try:
            copyfileobj(self.stream, dst, buffer_size)
        finally:
            if close_dst:
                dst.close()

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __nonzero__(self):
        return bool(self.filename and self.content_length)

    def __len__(self):
        return max(self.content_length, 0)

    def __iter__(self):
        return iter(self.readline, '')

    def __repr__(self):
        return '<%s: %r (%r)>' % (
            self.__class__.__name__,
            self.filename,
            self.content_type
        )


class Headers(object):
    """An object that stores some headers.  It has a dict like interface
    but is ordered and can store keys multiple times.

    This data structure is useful if you want a nicer way to handle WSGI
    headers which are stored as tuples in a list.

    From Werkzeug 0.3 onwards, the :exc:`KeyError` raised by this class is
    also a subclass of the :class:`~exceptions.BadRequest` HTTP exception
    and will render a page for a ``400 BAD REQUEST`` if catched in a
    catch-all for HTTP exceptions.

    Headers is mostly compatible with the Python :class:`wsgiref.headers.Headers`
    class, with the exception of `__getitem__`.  :mod:`wsgiref` will return
    `None` for ``headers['missing']``, whereas :class:`Headers` will raise
    a :class:`KeyError`.

    To create a new :class:`Headers` object pass it a list or dict of headers
    which are used as default values.  This does not reuse the list passed
    to the constructor for internal usage.  To create a :class:`Headers`
    object that uses as internal storage the list or list-like object you
    can use the :meth:`linked` class method.

    :param defaults: The list of default values for the :class:`Headers`.
    """

    # the key error this class raises.  Because of circular dependencies
    # with the http exception module this class is created at the end of
    # this module.
    KeyError = None

    def __init__(self, defaults=None, _list=None):
        if _list is None:
            _list = []
        self._list = _list
        if defaults is not None:
            self.extend(defaults)

    @classmethod
    def linked(cls, headerlist):
        """Create a new :class:`Headers` object that uses the list of headers
        passed as internal storage:

        >>> headerlist = [('Content-Length', '40')]
        >>> headers = Headers.linked(headerlist)
        >>> headers.add('Content-Type', 'text/html')
        >>> headerlist
        [('Content-Length', '40'), ('Content-Type', 'text/html')]

        :param headerlist: The list of headers the class is linked to.
        :return: new linked :class:`Headers` object.
        """
        return cls(_list=headerlist)

    def __getitem__(self, key, _index_operation=True):
        if _index_operation:
            if isinstance(key, (int, long)):
                return self._list[key]
            elif isinstance(key, slice):
                return self.__class__(self._list[key])
        ikey = key.lower()
        for k, v in self._list:
            if k.lower() == ikey:
                return v
        raise self.KeyError(key)

    def __eq__(self, other):
        return other.__class__ is self.__class__ and \
               set(other._list) == set(self._list)

    def __ne__(self, other):
        return not self.__eq__(other)

    def get(self, key, default=None, type=None):
        """Return the default value if the requested data doesn't exist.
        If `type` is provided and is a callable it should convert the value,
        return it or raise a :exc:`ValueError` if that is not possible.  In
        this case the function will return the default as if the value was not
        found:

        >>> d = Headers([('Content-Length', '42')])
        >>> d.get('Content-Length', type=int)
        42

        If a headers object is bound you must notadd unicode strings
        because no encoding takes place.

        :param key: The key to be looked up.
        :param default: The default value to be returned if the key can't
                        be looked up.  If not further specified `None` is
                        returned.
        :param type: A callable that is used to cast the value in the
                     :class:`Headers`.  If a :exc:`ValueError` is raised
                     by this callable the default value is returned.
        """
        try:
            rv = self.__getitem__(key, _index_operation=False)
        except KeyError:
            return default
        if type is None:
            return rv
        try:
            return type(rv)
        except ValueError:
            return default

    def getlist(self, key, type=None):
        """Return the list of items for a given key. If that key is not in the
        :class:`Headers`, the return value will be an empty list.  Just as
        :meth:`get` :meth:`getlist` accepts a `type` parameter.  All items will
        be converted with the callable defined there.

        :param key: The key to be looked up.
        :param type: A callable that is used to cast the value in the
                     :class:`Headers`.  If a :exc:`ValueError` is raised
                     by this callable the value will be removed from the list.
        :return: a :class:`list` of all the values for the key.
        """
        ikey = key.lower()
        result = []
        for k, v in self:
            if k.lower() == ikey:
                if type is not None:
                    try:
                        v = type(v)
                    except ValueError:
                        continue
                result.append(v)
        return result

    def get_all(self, name):
        """Return a list of all the values for the named field.

        This method is compatible with the :mod:`wsgiref`
        :meth:`~wsgiref.headers.Headers.get_all` method.
        """
        return self.getlist(name)

    def iteritems(self, lower=False):
        for key, value in self:
            if lower:
                key = key.lower()
            yield key, value

    def iterkeys(self, lower=False):
        for key, _ in self.iteritems(lower):
            yield key

    def itervalues(self):
        for _, value in self.iteritems():
            yield value

    def keys(self, lower=False):
        return list(self.iterkeys(lower))

    def values(self):
        return list(self.itervalues())

    def items(self, lower=False):
        return list(self.iteritems(lower))

    def extend(self, iterable):
        """Extend the headers with a dict or an iterable yielding keys and
        values.
        """
        if isinstance(iterable, dict):
            for key, value in iterable.iteritems():
                if isinstance(value, (tuple, list)):
                    for v in value:
                        self.add(key, v)
                else:
                    self.add(key, value)
        else:
            for key, value in iterable:
                self.add(key, value)

    def __delitem__(self, key, _index_operation=True):
        if _index_operation and isinstance(key, (int, long, slice)):
            del self._list[key]
            return
        key = key.lower()
        new = []
        for k, v in self._list:
            if k.lower() != key:
                new.append((k, v))
        self._list[:] = new

    def remove(self, key):
        """Remove a key.

        :param key: The key to be removed.
        """
        return self.__delitem__(key, _index_operation=False)

    def pop(self, key=None, default=_missing):
        """Removes and returns a key or index.

        :param key: The key to be popped.  If this is an integer the item at
                    that position is removed, if it's a string the value for
                    that key is.  If the key is omitted or `None` the last
                    item is removed.
        :return: an item.
        """
        if key is None:
            return self._list.pop()
        if isinstance(key, (int, long)):
            return self._list.pop(key)
        try:
            rv = self[key]
            self.remove(key)
        except KeyError:
            if default is not _missing:
                return default
            raise
        return rv

    def popitem(self):
        """Removes a key or index and returns a (key, value) item."""
        return self.pop()

    def __contains__(self, key):
        """Check if a key is present."""
        try:
            self.__getitem__(key, _index_operation=False)
        except KeyError:
            return False
        return True

    has_key = __contains__

    def __iter__(self):
        """Yield ``(key, value)`` tuples."""
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def add(self, _key, _value, **kw):
        """Add a new header tuple to the list.

        Keyword arguments can specify additional parameters for the header
        value, with underscores converted to dashes::

        >>> d = Headers()
        >>> d.add('Content-Type', 'text/plain')
        >>> d.add('Content-Disposition', 'attachment', filename='foo.png')

        The keyword argument dumping uses :func:`dump_options_header`
        behind the scenes.

        .. versionadded:: 0.4.1
            keyword arguments were added for :mod:`wsgiref` compatibility.
        """
        if kw:
            _value = dump_options_header(_value, dict((k.replace('_', '-'), v)
                                                      for k, v in kw.items()))
        self._list.append((_key, _value))

    def add_header(self, _key, _value, **_kw):
        """Add a new header tuple to the list.

        An alias for :meth:`add` for compatibility with the :mod:`wsgiref`
        :meth:`~wsgiref.headers.Headers.add_header` method.
        """
        self.add(_key, _value, **_kw)

    def clear(self):
        """Clears all headers."""
        del self._list[:]

    def set(self, key, value):
        """Remove all header tuples for `key` and add a new one.  The newly
        added key either appears at the end of the list if there was no
        entry or replaces the first one.

        :param key: The key to be inserted.
        :param value: The value to be inserted.
        """
        lc_key = key.lower()
        for idx, (old_key, old_value) in enumerate(self._list):
            if old_key.lower() == lc_key:
                # replace first ocurrence
                self._list[idx] = (key, value)
                break
        else:
            return self.add(key, value)
        self._list[idx + 1:] = [(k, v) for k, v in self._list[idx + 1:]
                                if k.lower() != lc_key]

    def setdefault(self, key, value):
        """Returns the value for the key if it is in the dict, otherwise it
        returns `default` and sets that value for `key`.

        :param key: The key to be looked up.
        :param default: The default value to be returned if the key is not
                        in the dict.  If not further specified it's `None`.
        """
        if key in self:
            return self[key]
        self.set(key, value)
        return value

    def __setitem__(self, key, value):
        """Like :meth:`set` but also supports index/slice based setting."""
        if isinstance(key, (slice, int, long)):
            self._list[key] = value
        else:
            self.set(key, value)

    def to_list(self, charset='utf-8'):
        """Convert the headers into a list and converts the unicode header
        items to the specified charset.

        :return: list
        """
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

    def __copy__(self):
        return self.copy()

    def __str__(self, charset='utf-8'):
        """Returns formatted headers suitable for HTTP transmission."""
        strs = []
        for key, value in self.to_list(charset):
            strs.append('%s: %s' % (key, value))
        strs.append('\r\n')
        return '\r\n'.join(strs)

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            list(self)
        )


class EnvironHeaders(Headers):
    """Read only version of the headers from a WSGI environment.  This
    provides the same interface as `Headers` and is constructed from
    a WSGI environment.

    From Werkzeug 0.3 onwards, the `KeyError` raised by this class is also a
    subclass of the :exc:`~exceptions.BadRequest` HTTP exception and will
    render a page for a ``400 BAD REQUEST`` if catched in a catch-all for
    HTTP exceptions.
    """

    def __init__(self, environ):
        self.environ = environ

    @classmethod
    def linked(cls, environ):
        raise TypeError('%r object is always linked to environment, '
                        'no separate initializer' % cls.__name__)

    def __eq__(self, other):
        return self is other

    def __getitem__(self, key, _index_operation=False):
        # _index_operation is a no-op for this class as there is no index but
        # used because get() calls it.
        key = key.upper().replace('-', '_')
        if key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            return self.environ[key]
        return self.environ['HTTP_' + key]

    def __iter__(self):
        for key, value in self.environ.iteritems():
            if key.startswith('HTTP_'):
                yield key[5:].replace('_', '-').title(), value
            elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                yield key.replace('_', '-').title(), value

    def copy(self):
        raise TypeError('cannot create %r copies' % self.__class__.__name__)

    def _immutable(self, *a, **kw):
        raise TypeError('%r is immutable' % self.__class__.__name__)
    remove = __delitem__ = add = clear = extend = set = __setitem__ = \
        _immutable
    del _immutable


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

    The optional `disallow` parameter can be a list of `fnmatch` rules for
    files that are not accessible from the web.  If `cache` is set to `False`
    no caching headers are sent.
    """

    # TODO: use wsgi.file_wrapper or something, just don't yield everything
    # at once.  Also consider switching to BaseResponse

    def __init__(self, app, exports, disallow=None, cache=True):
        self.app = app
        self.exports = {}
        self.cache = cache
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

    def get_file_loader(self, filename):
        return lambda x: (os.path.basename(filename), \
                          lambda: open(filename, 'rb'))

    def get_package_loader(self, package, package_path):
        from pkg_resources import resource_exists, resource_stream
        def loader(path):
            path = posixpath.join(package_path, path)
            if resource_exists(package, path):
                return posixpath.basename(path), \
                       lambda: resource_stream(package, path)
            return None, None
        return loader

    def get_directory_loader(self, directory):
        def loader(path):
            path = os.path.join(directory, path)
            if os.path.isfile(path):
                return os.path.basename(path), lambda: open(path, 'rb')
            return None, None
        return loader

    def __call__(self, environ, start_response):
        # sanitize the path for non unix systems
        cleaned_path = environ.get('PATH_INFO', '').strip('/')
        for sep in os.sep, os.altsep:
            if sep and sep != '/':
                cleaned_path = cleaned_path.replace(sep, '/')
        path = '/'.join([''] + [x for x in cleaned_path.split('/')
                                if x and x != '..'])
        stream_maker = None
        for search_path, loader in self.exports.iteritems():
            if search_path == path:
                real_filename, stream_maker = loader(None)
                if stream_maker is not None:
                    break
            if not search_path.endswith('/'):
                search_path += '/'
            if path.startswith(search_path):
                real_filename, stream_maker = loader(path[len(search_path):])
                if stream_maker is not None:
                    break
        if stream_maker is None or not self.is_allowed(real_filename):
            return self.app(environ, start_response)
        from mimetypes import guess_type
        guessed_type = guess_type(real_filename)
        mime_type = guessed_type[0] or 'text/plain'
        expiry = asctime(gmtime(time() + 3600))
        stream = stream_maker()
        try:
            data = stream.read()
        finally:
            stream.close()

        headers = [('Cache-Control', 'public')]
        if self.cache:
            etag = generate_etag(data)
            headers += [('Expires', expiry), ('ETag', etag)]
            if parse_etags(environ.get('HTTP_IF_NONE_MATCH')).contains(etag):
                remove_entity_headers(headers)
                start_response('304 Not Modified', headers)
                return []

        headers.extend((
            ('Content-Type', mime_type),
            ('Content-Length', str(len(data)))
        ))
        start_response('200 OK', headers)
        return [data]


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

    If there is just one close function it can be bassed instead of the list.

    A closing iterator is non needed if the application uses response objects
    and finishes the processing if the resonse is started::

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


class LimitedStream(object):
    """Wraps a stream so that it doesn't read more than n bytes.  If the
    stream is exhausted and the caller tries to get more bytes from it
    :func:`on_exhausted` is called which by default raises a
    :exc:`~werkzeug.exceptions.BadRequest`.  The return value of that
    function is forwarded to the reader function.  So if it returns an
    empty string :meth:`read` will return an empty string as well.

    The limit however must never be higher than what the stream can
    output.  Otherwise :meth:`readlines` will try to read past the
    limit.

    The `silent` parameter has no effect if :meth:`is_exhausted` is
    overriden by a subclass.

    :param stream: the stream to wrap.
    :param limit: the limit for the stream, must not be longer than
                  what the string can provide if the stream does not
                  end with `EOF` (like `wsgi.input`)
    :param silent: If set to `True` the stream will allow reading
                   past the limit and will return an empty string.
    """

    def __init__(self, stream, limit, silent=False):
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
        """Read a line from the stream.  Arguments are forwarded to the
        `readline` function of the underlaying stream if it supports
        them.
        """
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
    can be a `dict` or `MultiDict` (or any other dict subclass), otherwise
    the keyword arguments are used for the query parameters, cutting off
    the first trailing underscore of the parameter name:

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
        return Href(urlparse.urljoin(base, name), self.charset, self.sort,
                    self.key)

    def __call__(self, *path, **query):
        if path and isinstance(path[-1], dict):
            if query:
                raise TypeError('keyword arguments and query-dicts '
                                'can\'t be combined')
            query, path = path[-1], path[:-1]
        elif query:
            query = dict([(k.endswith('_') and k[:-1] or k, v)
                          for k, v in query.items()])
        path = '/'.join([url_quote(x, self.charset) for x in path
                         if x is not None]).lstrip('/')
        rv = self.base
        if path:
            if not rv.endswith('/'):
                rv += '/'
            rv = urlparse.urljoin(rv, path)
        if query:
            rv += '?' + url_encode(query, self.charset, sort=self.sort,
                                   key=self.key)
        return str(rv)


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

    .. versionchanged:: 0.5
       cached properties are now optionally writeable.
    """

    def __init__(self, func, name=None, doc=None, writeable=False):
        self.func = func
        self.writeable = writeable
        self.__name__ = name or func.__name__
        self.__doc__ = doc or func.__doc__

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value

    def __set__(self, obj, value):
        if not self.writeable:
            raise TypeError('read only attribute')
        obj.__dict__[self.__name__] = value

    @staticmethod
    def refresh(object, attributes):
        """Helper function that invalidates the property cache.  This can be
        useful if you have a function that changes a value that the cached
        one depends on::

            @cached_property
            def foo(self):
                return '%s/foo' % self.bar

            def change_bar(self):
                self.bar += 1
                cached_property.refresh(self, ['foo'])

        .. versionadded:: 0.5

        :param object: the object with the attributes
        :param attributes: an iterable with the attributes to refresh
        """
        for attribute in attributes:
            prop = getattr(object.__class__, attribute)
            assert isinstance(prop, cached_property), 'not a cached property'
            object.__dict__.pop(prop.__name__, None)


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


def parse_form_data(environ, stream_factory=None, charset='utf-8',
                    errors='ignore', max_form_memory_size=None,
                    max_content_length=None):
    """Parse the form data in the environ and return it as tuple in the form
    ``(stream, form, files)``.  You should only call this method if the
    transport method is `POST` or `PUT`.

    If the mimetype of the data transmitted is `multipart/form-data` the
    files multidict will be filled with `FileStorage` objects.  If the
    mimetype is unknow the input stream is wrapped and returned as first
    argument, else the stream is empty.

    This function does not raise exception, even if the input data is
    malformed.

    Have a look at :ref:`dealing-with-request-data` for more details.

    .. versionadded:: 0.5
       The `max_form_memory_size` and `max_content_length` parameters were added.

    :param environ: the WSGI environment to be used for parsing.
    :param stream_factory: An optional callable that returns a new read and
                           writeable file descriptor.  This callable works
                           the same as :meth:`~BaseResponse._get_file_stream`.
    :param charset: The character set for URL and url encoded form data.
    :param errors: The encoding error behavior.
    :param max_form_memory_size: the maximum number of bytes to be accepted for
                           in-memory stored form data.  If the data
                           exceeds the value specified a
                           :exc:`~exceptions.RequestURITooLarge`
                           exception is raised.
    :param max_content_length: If this is provided and the transmitted data
                               is longer than this value a
                               :exc:`~exceptions.RequestEntityTooLarge`
                               exception is raised.
    :return: A tuple in the form ``(stream, form, files)``.
    """
    content_type, extra = parse_options_header(environ.get('CONTENT_TYPE', ''))
    try:
        content_length = int(environ['CONTENT_LENGTH'])
    except (KeyError, ValueError):
        content_length = 0

    if max_content_length is not None and content_length > max_content_length:
        raise RequestEntityTooLarge()

    stream = _empty_stream
    form = files = ()

    if content_type == 'multipart/form-data':
        try:
            form, files = parse_multipart(environ['wsgi.input'],
                                          extra.get('boundary'),
                                          content_length, stream_factory,
                                          charset, errors,
                                          max_form_memory_size=max_form_memory_size)
        except ValueError, e:
            pass
    elif content_type == 'application/x-www-form-urlencoded' or \
         content_type == 'application/x-url-encoded':
        if max_form_memory_size is not None and \
           content_length > max_form_memory_size:
            raise RequestEntityTooLarge()
        form = url_decode(environ['wsgi.input'].read(content_length),
                          charset, errors=errors)
    else:
        stream = LimitedStream(environ['wsgi.input'], content_length,
                               silent=True)

    return stream, MultiDict(form), MultiDict(files)


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


def url_decode(s, charset='utf-8', decode_keys=False, include_empty=True,
               errors='ignore', separator='&'):
    """Parse a querystring and return it as :class:`MultiDict`.  Per default
    only values are decoded into unicode strings.  If `decode_keys` is set to
    `True` the same will happen for keys.

    Per default a missing value for a key will default to an empty key.  If
    you don't want that behavior you can set `include_empty` to `False`.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.

    .. versionchanged:: 0.5
       In previous versions ";" and "&" could be used for url decoding.
       This changed in 0.5 where only "&" is supported.  If you want to
       use ";" instead a different `separator` can be provided.

    :param s: a string with the query string to decode.
    :param charset: the charset of the query string.
    :param decode_keys: set to `True` if you want the keys to be decoded
                        as well.
    :param include_empty: Set to `False` if you don't want empty values to
                          appear in the dict.
    :param errors: the decoding error behavior.
    :param separator: the pair separator to be used, defaults to ``&``
    """
    result = []
    for pair in str(s).split(separator):
        if not pair:
            continue
        if '=' in pair:
            key, value = pair.split('=', 1)
        else:
            key = pair
            value = ''
        key = urllib.unquote_plus(key)
        if decode_keys:
            key = _decode_unicode(key, charset, errors)
        result.append((key, url_unquote_plus(value, charset, errors)))
    return MultiDict(result)


def url_encode(obj, charset='utf-8', encode_keys=False, sort=False, key=None,
               separator='&'):
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
    if isinstance(obj, MultiDict):
        items = obj.lists()
    elif isinstance(obj, dict):
        items = []
        for k, v in obj.iteritems():
            if not isinstance(v, (tuple, list)):
                v = [v]
            items.append((k, v))
    else:
        items = obj or ()
    if sort:
        items.sort(key=key)
    tmp = []
    for key, values in items:
        if encode_keys and isinstance(key, unicode):
            key = key.encode(charset)
        else:
            key = str(key)
        for value in values:
            if value is None:
                continue
            elif isinstance(value, unicode):
                value = value.encode(charset)
            else:
                value = str(value)
            tmp.append('%s=%s' % (urllib.quote(key),
                                  urllib.quote_plus(value)))
    return separator.join(tmp)


def url_quote(s, charset='utf-8', safe='/:'):
    """URL encode a single string with a given encoding.

    :param s: the string to quote.
    :param charset: the charset to be used.
    :param safe: an optional sequence of safe characters.
    """
    if isinstance(s, unicode):
        s = s.encode(charset)
    elif not isinstance(s, str):
        s = str(s)
    return urllib.quote(s, safe=safe)


def url_quote_plus(s, charset='utf-8', safe=''):
    """URL encode a single string with the given encoding and convert
    whitespace to "+".

    :param s: the string to quote.
    :param charset: the charset to be used.
    :param safe: an optional sequence of safe characters.
    """
    if isinstance(s, unicode):
        s = s.encode(charset)
    elif not isinstance(s, str):
        s = str(s)
    return urllib.quote_plus(s, safe=safe)


def url_unquote(s, charset='utf-8', errors='ignore'):
    """URL decode a single string with a given decoding.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.

    :param s: the string to unquote.
    :param charset: the charset to be used.
    :param errors: the error handling for the charset decoding.
    """
    return _decode_unicode(urllib.unquote(s), charset, errors)


def url_unquote_plus(s, charset='utf-8', errors='ignore'):
    """URL decode a single string with the given decoding and decode
    a "+" to whitespace.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.

    :param s: the string to unquote.
    :param charset: the charset to be used.
    :param errors: the error handling for the charset decoding.
    """
    return _decode_unicode(urllib.unquote_plus(s), charset, errors)


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
    if isinstance(s, unicode):
        s = s.encode(charset, 'ignore')
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urllib.quote(path, '/%')
    qs = urllib.quote_plus(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


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


def get_current_url(environ, root_only=False, strip_querystring=False,
                    host_only=False):
    """A handy helper function that recreates the full URL for the current
    request or parts of it.  Here an example:

    >>> env = create_environ("/?param=foo", "http://localhost/script")
    >>> get_current_url(env)
    'http://localhost/script/?param=foo'
    >>> get_current_url(env, root_only=True)
    'http://localhost/script/'
    >>> get_current_url(env, host_only=True)
    'http://localhost/'
    >>> get_current_url(env, strip_querystring=True)
    'http://localhost/script/'

    :param environ: the WSGI environment to get the current URL of.
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


def parse_cookie(header, charset='utf-8', errors='ignore'):
    """Parse a cookie.  Either from a string or WSGI environ.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    :exc:`HTTPUnicodeError` is raised.

    :param header: the header to be used to parse the cookie.  Alternatively
                   this can be a WSGI environment.
    :param charset: the charset for the cookie values.
    :param errors: the error behavior for the charset decoding.
    """
    if isinstance(header, dict):
        header = header.get('HTTP_COOKIE', '')
    cookie = _ExtendedCookie()
    cookie.load(header)
    result = {}

    # decode to unicode and skip broken items.  Our extended morsel
    # and extended cookie will catch CookieErrors and convert them to
    # `None` items which we have to skip here.
    for key, value in cookie.iteritems():
        if value.value is not None:
            result[key] = _decode_unicode(value.value, charset, errors)

    return result


def dump_cookie(key, value='', max_age=None, expires=None, path='/',
                domain=None, secure=None, httponly=False, charset='utf-8',
                sync_expires=True):
    """Creates a new Set-Cookie header without the ``Set-Cookie`` prefix
    The parameters are the same as in the cookie Morsel object in the
    Python standard library but it accepts unicode data too.

    :param max_age: should be a number of seconds, or `None` (default) if
                    the cookie should last only as long as the client's
                    browser session.  Additionally `timedelta` objects
                    are accepted too.
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
    query_string = environ['QUERY_STRING']
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
    """Imports an object based on a string.  This use useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).

    If the `silent` is True the return value will be `None` if the import
    fails.

    :param import_name: the dotted name for the object to import.
    :param silent: if set to `True` import errors are ignored and
                   `None` is returned instead.
    :return: imported object
    """
    try:
        if ':' in import_name:
            module, obj = import_name.split(':', 1)
        elif '.' in import_name:
            items = import_name.split('.')
            module = '.'.join(items[:-1])
            obj = items[-1]
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
    :param include_packages: set to `True` if packages should be returned too.
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


def create_environ(path='/', base_url=None, query_string=None, method='GET',
                   input_stream=None, content_type=None, content_length=0,
                   errors_stream=None, multithread=False,
                   multiprocess=False, run_once=False):
    """Create a new WSGI environ dict based on the values passed.  The first
    parameter should be the path of the request which defaults to '/'.  The
    second one can either be a absolute path (in that case the host is
    localhost:80) or a full path to the request with scheme, netloc port and
    the path to the script.

    If the `path` contains a query string it will be used, even if the
    `query_string` parameter was given.  If it does not contain one
    the `query_string` parameter is used as querystring.  In that case
    it can either be a dict, :class:`MultiDict` or string.

    The following options exist:

    :param path: the path of the request.  See explanation above.
    :param method: the request method.
    :param input_stream: the input stream.  Defaults to an empty read only
                         stream.
    :param content_type: the content type for this request.
    :param content_length: the value for the content length header.
    :param errors_stream: the wsgi.errors stream.  Defaults to `sys.stderr`.
    :param multithread: the multithreaded flag for the WSGI environment.
    :param multiprocess: the multiprocess flag for the WSGI environment.
    :param run_once: the run_once flag for the WSGI environment.
    """
    if base_url is not None:
        scheme, netloc, script_name, qs, fragment = urlparse.urlsplit(base_url)
        if ':' in netloc:
            server_name, server_port = netloc.split(':')
        else:
            if scheme == 'http':
                server_port = '80'
            elif scheme == 'https':
                server_port = '443'
            else:
                server_port = ''
            server_name = netloc
        if qs or fragment:
            raise ValueError('base url cannot contain a query string '
                             'or fragment')
        script_name = urllib.unquote(script_name) or ''
    else:
        scheme = 'http'
        server_name = netloc = 'localhost'
        server_port = '80'
        script_name = ''
    if path and '?' in path:
        path, query_string = path.split('?', 1)
    elif not isinstance(query_string, basestring):
        query_string = url_encode(query_string)
    path = urllib.unquote(path) or '/'

    return {
        'REQUEST_METHOD':       method,
        'SCRIPT_NAME':          script_name,
        'PATH_INFO':            path,
        'QUERY_STRING':         query_string,
        'SERVER_NAME':          server_name,
        'SERVER_PORT':          server_port,
        'HTTP_HOST':            netloc,
        'SERVER_PROTOCOL':      'HTTP/1.0',
        'CONTENT_TYPE':         content_type or '',
        'CONTENT_LENGTH':       str(content_length),
        'wsgi.version':         (1, 0),
        'wsgi.url_scheme':      scheme,
        'wsgi.input':           input_stream or _empty_stream,
        'wsgi.errors':          errors_stream or sys.stderr,
        'wsgi.multithread':     multithread,
        'wsgi.multiprocess':    multiprocess,
        'wsgi.run_once':        run_once
    }


def run_wsgi_app(app, environ, buffered=False):
    """Return a tuple in the form (app_iter, status, headers) of the
    application output.  This works best if you pass it an application that
    returns a iterator all the time.

    Sometimes applications may use the `write()` callable returned
    by the `start_response` function.  This tries to resolve such edge
    cases automatically.  But if you don't get the expected output you
    should set `buffered` to `True` which enforces buffering.

    If passed an invalid WSGI application the behavior of this function is
    undefined.  Never pass non-conforming WSGI applications to this function.

    :param app: the application to execute.
    :param buffered: set to `True` to enforce buffering.
    :return:
    """
    response = []
    buffer = []

    def start_response(status, headers, exc_info=None):
        if exc_info is not None:
            raise exc_info[0], exc_info[1], exc_info[2]
        response[:] = [status, headers]
        return buffer.append

    app_iter = app(environ, start_response)

    # when buffering we emit the close call early and conver the
    # application iterator into a regular list
    if buffered:
        close_func = getattr(app_iter, 'close', None)
        try:
            app_iter = list(app_iter)
        finally:
            if close_func is not None:
                close_func()

    # otherwise we iterate the application iter until we have
    # a response, chain the already received data with the already
    # collected data and wrap it in a new `ClosingIterator` if
    # we have a close callable.
    else:
        while not response:
            buffer.append(app_iter.next())
        if buffer:
            app_iter = chain(buffer, app_iter)
            close_func = getattr(app_iter, 'close', None)
            if close_func is not None:
                app_iter = ClosingIterator(app_iter, close_func)

    return app_iter, response[0], response[1]


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


# circurlar dependency fun
from werkzeug.http import generate_etag, parse_etags, \
     remove_entity_headers, parse_multipart, parse_options_header, \
     dump_options_header

# create all the special key errors now that the classes are defined.
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
for _cls in MultiDict, CombinedMultiDict, Headers, EnvironHeaders:
    _cls.KeyError = BadRequest.wrap(KeyError, _cls.__name__ + '.KeyError')
del _cls
