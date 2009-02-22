# -*- coding: utf-8 -*-
"""
    werkzeug.datastructures
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module provides mixins and classes with an immutable interface.

    :copyright: Copyright 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug._internal import _proxy_repr, _missing


def is_immutable(self):
    raise TypeError('%r objects are immutable' % self.__class__.__name__)


class ImmutableListMixin(object):
    """Makes a :class:`list` immutable.

    .. versionadded:: 0.5

    :private:
    """

    def __delitem__(self, key):
        is_immutable(self)

    def __delslice__(self, i, j):
        is_immutable(self)

    def __iadd__(self, other):
        is_immutable(self)
    __imul__ = __iadd__

    def __setitem__(self, key, value):
        is_immutable(self)

    def __setslice__(self, i, j, value):
        is_immutable(self)

    def append(self, item):
        is_immutable(self)
    remove = append

    def extend(self, iterable):
        is_immutable(self)

    def insert(self, pos, value):
        is_immutable(self)

    def pop(self, index=-1):
        is_immutable(self)

    def reverse(self):
        is_immutable(self)

    def sort(self, cmp=None, key=None, reverse=None):
        is_immutable(self)


class ImmutableList(ImmutableListMixin, list):
    """An immutable :class:`list`.

    .. versionadded:: 0.5

    :private:
    """

    __repr__ = _proxy_repr(list)


class ImmutableDictMixin(object):
    """Makes a :class:`dict` immutable.

    .. versionadded:: 0.5

    :private:
    """

    def setdefault(self, key, default=None):
        is_immutable(self)

    def update(self, *args, **kwargs):
        is_immutable(self)

    def pop(self, key, default=None):
        is_immutable(self)

    def popitem(self):
        is_immutable(self)

    def __setitem__(self, key, value):
        is_immutable(self)

    def __delitem__(self, key):
        is_immutable(self)

    def clear(self):
        is_immutable(self)


class ImmutableMultiDictMixin(ImmutableDictMixin):
    """Makes a :class:`MultiDict` immutable.

    .. versionadded:: 0.5

    :private:
    """

    def popitemlist(self):
        is_immutable(self)

    def poplist(self, key):
        is_immutable(self)

    def setlist(self, key, new_list):
        is_immutable(self)

    def setlistdefault(self, key, default_list=None):
        is_immutable(self)


class TypeConversionDict(dict):
    """Works like a regular dict but the :meth:`get` method can perform
    type conversions.  :class:`MultiDict` and :class:`CombinedMultiDict`
    are subclasses of this class and provide the same feature.

    .. versionadded:: 0.5
    """

    def get(self, key, default=None, type=None):
        """Return the default value if the requested data doesn't exist.
        If `type` is provided and is a callable it should convert the value,
        return it or raise a :exc:`ValueError` if that is not possible.  In
        this case the function will return the default as if the value was not
        found:

        >>> d = TypeConversionDict(foo='42', bar='blub')
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


class ImmutableTypeConversionDict(ImmutableDictMixin, TypeConversionDict):
    """Works like a :class:`TypeConversionDict` but does not support
    modifications.

    .. versionadded:: 0.5
    """


class MultiDict(TypeConversionDict):
    """A :class:`MultiDict` is a dictionary subclass customized to deal with
    multiple values for the same key which is for example used by the parsing
    functions in the wrappers.  This is necessary because some HTML form
    elements pass multiple values for the same key.

    :class:`MultiDict` implements all standard dictionary methods.
    Internally, it saves all values for a key as a list, but the standard dict
    access methods will only return the first value for a key. If you want to
    gain access to the other values, too, you have to use the `list` methods as
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
    ``(key, value)`` tuples, a dict, a :class:`MultiDict` or from Werkzeug 0.2
    onwards some keyword parameters.

    :param mapping: the initial value for the :class:`MultiDict`.  Either a
                    regular dict, an iterable of ``(key, value)`` tuples
                    or `None`.
    """

    # internal list type.  This is an internal interface!  do not use.
    # it's only used in methods that do not modify the multi dict so that
    # ImmutableMultiDict can use it without much hassle.
    _list_type = list

    # the key error this class raises.  Because of circular dependencies
    # with the http exception module this class is created at the end of
    # this module.
    KeyError = None

    def __init__(self, mapping=None):
        if isinstance(mapping, MultiDict):
            dict.__init__(self, ((k, self._list_type(v))
                          for k, v in mapping.lists()))
        elif isinstance(mapping, dict):
            tmp = {}
            for key, value in mapping.iteritems():
                if isinstance(value, (tuple, list)):
                    value = self._list_type(value)
                else:
                    value = self._list_type([value])
                tmp[key] = value
            dict.__init__(self, tmp)
        else:
            tmp = {}
            for key, value in mapping or ():
                tmp.setdefault(key, []).append(value)
            dict.__init__(self, (dict((k, self._list_type(v))
                                 for k, v in tmp.iteritems())))

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
            return self._list_type()
        if type is None:
            return rv
        result = []
        for item in rv:
            try:
                result.append(type(item))
            except ValueError:
                pass
        return self._list_type(result)

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
    #: all values associated with the key.
    #:
    #: :return: a :class:`list`
    lists = dict.items

    def values(self):
        """Returns a list of the first value on every key's value list.

        :return: a :class:`list`.
        """
        return [self[key] for key in self.iterkeys()]

    #: Return a list of all values associated with a key.  Zipping
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

    #: Return a list of all values associated with a key.
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
                     contain the first value for each key.
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


class Headers(object):
    """An object that stores some headers.  It has a dict-like interface
    but is ordered and can store the same keys multiple times.

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

        If a headers object is bound you must not add unicode strings
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


class ImmutableHeadersMixin(object):
    """Makes a :class:`Headers` immutable.

    .. versionadded:: 0.5
    """

    def __delitem__(self, key):
        is_immutable(self)

    def __setitem__(self, key, value):
        is_immutable(self)
    set = __setitem__

    def add(self, item):
        is_immutable(self)
    remove = add_header = add

    def extend(self, iterable):
        is_immutable(self)

    def insert(self, pos, value):
        is_immutable(self)

    def pop(self, index=-1):
        is_immutable(self)

    def popitem(self):
        is_immutable(self)

    def setdefault(self, key, default):
        is_immutable(self)


class EnvironHeaders(ImmutableHeadersMixin, Headers):
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


class CombinedMultiDict(ImmutableMultiDictMixin, MultiDict):
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

    _list_type = ImmutableList

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
        return self._list_type(rv)

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


class ImmutableDict(ImmutableDictMixin, dict):
    """An immutable :class:`dict`.

    .. versionadded:: 0.5
    """

    __repr__ = _proxy_repr(dict)


class ImmutableMultiDict(ImmutableMultiDictMixin, MultiDict):
    """An immutable :class:`MultiDict`.  The methods that return the internal
    lists return :class:`ImmutableList` objects.

    .. versionadded:: 0.5
    """

    _list_type = ImmutableList


# circular dependencies
from werkzeug.http import dump_options_header


# create all the special key errors now that the classes are defined.
from werkzeug.exceptions import BadRequest
for _cls in MultiDict, CombinedMultiDict, Headers, EnvironHeaders:
    _cls.KeyError = BadRequest.wrap(KeyError, _cls.__name__ + '.KeyError')
del _cls
