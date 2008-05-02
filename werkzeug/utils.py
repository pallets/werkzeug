# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    This module implements various utilities for WSGI applications.  Most of
    them are used by the request and response wrappers but especially for
    middleware development it makes sense to use them without the wrappers.

    :copyright: 2007-2008 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
import sys
import cgi
import urllib
import urlparse
import posixpath
from itertools import chain
from time import asctime, gmtime, time
from datetime import timedelta
try:
    set = set
except NameError:
    from sets import Set as set
    def reversed(item):
        return item[::-1]
from werkzeug._internal import _patch_wrapper, _decode_unicode, \
     _empty_stream, _iter_modules, _ExtendedCookie, _ExtendedMorsel, \
     _StorageHelper, _DictAccessorProperty, _dump_date
from werkzeug.http import generate_etag


_format_re = re.compile(r'\$(%s|\{%s\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))
_entity_re = re.compile(r'&([^;]+);')


class MultiDict(dict):
    """A `MultiDict` is a dictionary subclass customized to deal with multiple
    values for the same key which is for example used by the parsing functions
    in the wrappers.  This is necessary because some HTML form elements pass
    multiple values for the same key.

    `MultiDict` implements the all standard dictionary methods.  Internally,
    it saves all values for a key as a list, but the standard dict access
    methods will only return the first value for a key. If you want to gain
    access to the other values too you have to use the `list` methods as
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
    subclass of the `BadRequest` HTTP exception and will render a page for a
    ``400 BAD REQUEST`` if catched in a catch-all for HTTP exceptions.
    """

    #: the key error this class raises.  Because of circular dependencies
    #: with the http exception module this class is created at the end of
    #: this module.
    KeyError = None

    def __init__(self, mapping=()):
        """A `MultiDict` can be constructed from an iterable of
        ``(key, value)`` tuples, a dict, a `MultiDict` or with Werkzeug 0.2
        onwards some keyword parameters.
        """
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
            for key, value in mapping:
                tmp.setdefault(key, []).append(value)
            dict.__init__(self, tmp)

    def __getitem__(self, key):
        """Return the first data value for this key;
        raises KeyError if not found.

        :raise KeyError: if the key does not exist
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
        return it or raise a `ValueError` if that is not possible.  In this
        case the function will return the default as if the value was not
        found.

        Example:

        >>> d = MultiDict(foo='42', bar='blub')
        >>> d.get('foo', type=int)
        42
        >>> d.get('bar', -1, type=int)
        -1
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

        :return: list
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

        >>> multidict.setlist('foo', ['1', '2'])
        >>> multidict['foo']
        '1'
        >>> multidict.getlist('foo')
        ['1', '2']
        """
        dict.__setitem__(self, key, list(new_list))

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        else:
            default = self[key]
        return default

    def setlistdefault(self, key, default_list=()):
        """Like `setdefault` but sets multiple values."""
        if key not in self:
            default_list = list(default_list)
            dict.__setitem__(self, key, default_list)
        else:
            default_list = self.getlist(key)
        return default_list

    def items(self):
        """Return a list of (key, value) pairs, where value is the last item
        in the list associated with the key.
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

    def to_dict(self, flat=True):
        """Return the contents as regular dict.  If `flat` is `True` the
        returned dict will only have the first item present, if `flat` is
        `False` all values will be returned as lists.

        :return: dict
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
    """A read only `MultiDict` decorator that you can pass multiple `MultiDict`
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
    subclass of the `BadRequest` HTTP exception and will render a page for a
    ``400 BAD REQUEST`` if catched in a catch-all for HTTP exceptions.
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
        """Returns the contents as simple dict.  If `flat` is `True` the
        resulting dict will only have the first item present, if `flat`
        is `False` all values will be lists.
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
    """The `FileStorage` object is a thin wrapper over incoming files.  It is
    used by the request object to represent uploaded files.  All the
    attributes of the wrapper stream are proxied by the file storage so
    it's possible to do ``storage.read()`` instead of the long form
    ``storage.stream.read()``.
    """

    def __init__(self, stream=None, filename=None, name=None,
                 content_type='application/octet-stream', content_length=-1):
        """Creates a new `FileStorage` object.

        :param stream: the input stream for uploaded file.  Usually this
                       points to a temporary file.
        :param filename: The filename of the file on the client.
        :param name: the name of the form field
        :param content_type: the content type of the file
        :param content_length: the content length of the file.
        """
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

    From Werkzeug 0.3 onwards, the `KeyError` raised by this class is also a
    subclass of the `BadRequest` HTTP exception and will render a page for a
    ``400 BAD REQUEST`` if catched in a catch-all for HTTP exceptions.
    """

    #: the key error this class raises.  Because of circular dependencies
    #: with the http exception module this class is created at the end of
    #: this module.
    KeyError = None

    def __init__(self, defaults=None, _list=None):
        """Create a new `Headers` object based on a list or dict of headers
        which are used as default values.  This does not reuse the list passed
        to the constructor for internal usage.  To create a `Headers` object
        that uses as internal storage the list or list-like object provided
        it's possible to use the `linked` classmethod.
        """
        if _list is None:
            _list = []
        self._list = _list
        if isinstance(defaults, dict):
            for key, value in defaults.iteritems():
                if isinstance(value, (tuple, list)):
                    for v in value:
                        self._list.append((key, v))
                else:
                    self._list.append((key, value))
        elif defaults is not None:
            self._list[:] = defaults

    def linked(cls, headerlist):
        """Create a new `Headers` object that uses the list of headers passed
        as internal storage:

        >>> headerlist = [('Content-Length', '40')]
        >>> headers = Headers.linked(headerlist)
        >>> headers.add('Content-Type', 'text/html')
        >>> headerlist
        [('Content-Length', '40'), ('Content-Type', 'text/html')]

        :return: new linked `Headers` object.
        """
        return cls(_list=headerlist)
    linked = classmethod(linked)

    def __getitem__(self, key):
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
        return it or raise a `ValueError` if that is not possible.  In this
        case the function will return the default as if the value was not
        found.

        Example:

        >>> d = Headers([('Content-Length', '42')])
        >>> d.get('Content-Length', type=int)
        42

        If a headers object is bound you must notadd unicode strings
        because no encoding takes place.
        """
        try:
            rv = self[key]
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
        `MultiDict`, the return value will be an empty list.  Just as `get`
        `getlist` accepts a `type` parameter.  All items will be converted
        with the callable defined there.

        :return: list
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
            iterable = iterable.iteritems()
        for key, value in iterable:
            self.add(key, value)

    def __delitem__(self, key):
        key = key.lower()
        new = []
        for k, v in self._list:
            if k.lower() != key:
                new.append((k, v))
        self._list[:] = new

    remove = __delitem__

    def __contains__(self, key):
        """Check if a key is present."""
        try:
            self[key]
        except KeyError:
            return False
        return True

    has_key = __contains__

    def __iter__(self):
        """Yield ``(key, value)`` tuples."""
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
        lc_key = key.lower()
        for idx, (old_key, old_value) in enumerate(self._list):
            if old_key.lower() == lc_key:
                self._list[idx] = (key, value)
                return
        self.add(key, value)

    __setitem__ = set

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
    subclass of the `BadRequest` HTTP exception and will render a page for a
    ``400 BAD REQUEST`` if catched in a catch-all for HTTP exceptions.
    """

    def __init__(self, environ):
        self.environ = environ

    def linked(cls, environ):
        raise TypeError('%r object is always linked to environment, '
                        'no separate initializer' % self.__class__.__name__)
    linked = classmethod(linked)

    def __eq__(self, other):
        return self is other

    def __getitem__(self, key):
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
    python package.
    """

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
        headers = [('Content-Type', mime_type), ('Cache-Control', 'public')]
        if self.cache:
            headers += [('Expires', expiry), ('ETag', generate_etag(data))]

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

    Accessing attributes on the href object creates a new href object with
    the attribute name as prefix:

    >>> bar_href = href.bar
    >>> bar_href("blub")
    '/foo/bar/blub'
    """

    def __init__(self, base='./', charset='utf-8'):
        if not base:
            base = './'
        self.base = base
        self.charset = charset

    def __getattr__(self, name):
        if name[:2] == '__':
            raise AttributeError(name)
        base = self.base
        if base[-1:] != '/':
            base += '/'
        return Href(urlparse.urljoin(base, name), self.charset)

    def __call__(self, *path, **query):
        if query:
            if path and isinstance(path[-1], dict):
                query, path = path[-1], path[:-1]
            else:
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
            rv += '?' + url_encode(query, self.charset)
        return str(rv)


class cached_property(object):
    """A decorator that converts a function into a lazy property. The
    function wrapped is called the first time to retrieve the result
    and than that calculated result is used the next time you access
    the value::

        class Foo(object):

            @cached_property
            def foo(self):
                # calculate something important here
                return 42
    """

    def __init__(self, func, name=None, doc=None):
        self.func = func
        self.__name__ = name or func.__name__
        self.__doc__ = doc or func.__doc__

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = self.func(obj)
        setattr(obj, self.__name__, value)
        return value


class environ_property(_DictAccessorProperty):
    """Maps request attributes to environment variables. This works not only
    for the Werzeug request object, but also any other class with an
    environ attribute:

    >>> class test_p(object):
    ...     environ = { 'test': 'test' }
    ...     test = environ_property('test')
    >>> var = test_p()
    >>> var.test
    test

    If you pass it a second value it's used as default if the key does not
    exist, the third one can be a converter that takes a value and converts
    it.  If it raises `ValueError` or `TypeError` the default value is used.
    If no default value is provided `None` is used.

    Per default the property works in two directions, but if you set
    `read_only` to False it will block set/delete.
    """

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
    '<p class="foo"><a href="foo.html">foo</a> <a href="bar.html">bar</a></p>'

    This class works around some browser limitations and can not be used for
    arbitrary SGML/XML generation.  For that purpose lxml and similar
    libraries exist.

    Calling the builder escapes the string passed:

    >>> html.p(html("<foo>"))
    '<p>&lt;foo&gt;</p>'
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
                    value = self._dialect == 'xhtml' and '="%s"' % key or ''
                else:
                    value = '="%s"' % escape(value, True)
                write(' ' + key + value)
            if not children and tag in self._empty_elements:
                write(self._dialect == 'xhtml' and ' />' or '>')
                return ''.join(buffer)
            write('>')
            children_as_string = ''.join(children)
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
                    errors='ignore'):
    """Parse the form data in the environ and return it as tuple in the form
    ``(stream, form, files)``.  You should only call this method if the
    transport method is `POST` or `PUT`.

    If the mimetype of the data transmitted is `multipart/form-data` the
    files multidict will be filled with `FileStorage` objects.  If the
    mimetype is unknow the input stream is wrapped and returned as first
    argument, else the stream is empty.
    """
    stream = _empty_stream
    form = []
    files = []
    storage = _StorageHelper(environ, stream_factory)
    if storage.file:
        stream = storage.file
    if storage.list is not None:
        for key in storage.keys():
            values = storage[key]
            if not isinstance(values, list):
                values = [values]
            for item in values:
                if getattr(item, 'filename', None) is not None:
                    fn = _decode_unicode(item.filename, charset, errors)
                    # fix stupid IE bug (IE6 sends the whole path)
                    if fn[1:3] == ':\\' or fn[:2] == '\\\\':
                        fn = fn.split('\\')[-1]
                    files.append((key, FileStorage(item.file, fn, key,
                                  item.type, item.length)))
                else:
                    form.append((key, _decode_unicode(item.value,
                                 charset, errors)))
    return stream, MultiDict(form), MultiDict(files)


def get_content_type(mimetype, charset):
    """Return the full content type string with charset for a mimetype.

    If the mimetype represents text the charset will be appended as charset
    parameter, otherwise the mimetype is returned unchanged.
    """
    if mimetype.startswith('text/') or \
       mimetype == 'application/xml' or \
       (mimetype.startswith('application/') and
        mimetype.endswith('+xml')):
        mimetype += '; charset=' + charset
    return mimetype


def format_string(string, context):
    """String-template format a string::

        >>> format_string('$foo and ${foo}s', dict(foo=42))
        '42 and 42s'

    This does not do any attribute lookup etc.  For more advanced string
    formattings have a look at the `werkzeug.template` module.
    """
    def lookup_arg(match):
        x = context[match.group(1)]
        if not isinstance(x, basestring):
            x = type(string)(x)
        return x
    return _format_re.sub(lookup_arg, string)


def url_decode(s, charset='utf-8', decode_keys=False, include_empty=True,
               errors='ignore'):
    """Parse a querystring and return it as `MultiDict`.  Per default only
    values are decoded into unicode strings.  If `decode_keys` is set to
    ``True`` the same will happen for keys.

    Per default a missing value for a key will default to an empty key.  If
    you don't want that behavior you can set `include_empty` to `False`.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.
    """
    tmp = []
    for key, values in cgi.parse_qs(str(s), include_empty).iteritems():
        for value in values:
            if decode_keys:
                key = _decode_unicode(key, charset, errors)
            tmp.append((key, _decode_unicode(value, charset, errors)))
    return MultiDict(tmp)


def url_encode(obj, charset='utf-8', encode_keys=False):
    """URL encode a dict/`MultiDict`.  If a value is `None` it will not appear
    in the result string.  Per default only values are encoded into the target
    charset strings.  If `encode_keys` is set to ``True`` unicode keys are
    supported too.
    """
    if isinstance(obj, MultiDict):
        items = obj.lists()
    elif isinstance(obj, dict):
        items = []
        for key, value in obj.iteritems():
            if not isinstance(value, (tuple, list)):
                value = [value]
            items.append((key, value))
    else:
        items = obj or ()
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
    return '&'.join(tmp)


def url_quote(s, charset='utf-8', safe='/:'):
    """URL encode a single string with a given encoding."""
    if isinstance(s, unicode):
        s = s.encode(charset)
    elif not isinstance(s, str):
        s = str(s)
    return urllib.quote(s, safe=safe)


def url_quote_plus(s, charset='utf-8', safe=''):
    """URL encode a single string with the given encoding and convert
    whitespace to "+".
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
    """
    return _decode_unicode(urllib.unquote(s), charset, errors)


def url_unquote_plus(s, charset='utf-8', errors='ignore'):
    """URL decode a single string with the given decoding and decode
    a "+" to whitespace.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.
    """
    return _decode_unicode(urllib.unquote_plus(s), charset, errors)


def url_fix(s, charset='utf-8'):
    """Sometimes you get an URL by a user that just isn't a real URL because
    it contains unsafe characters like ' ' and so on.  This function can fix
    some of the problems in a similar way browsers handle data entered by the
    user:

    >>> url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)')
    'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

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
    """Return the real host for the given WSGI enviornment.  This takes care
    of the `X-Forwarded-Host` header.
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


def cookie_date(expires=None):
    """Formats the time to ensure compatibility with Netscape's cookie
    standard.

    Accepts a floating point number expressed in seconds since the epoc in, a
    datetime object or a timetuple.  All times in UTC.  The `parse_date`
    function in `werkzeug.http` can be used to parse such a date.

    Outputs a string in the format ``Wdy, DD-Mon-YYYY HH:MM:SS GMT``.
    """
    return _dump_date(expires, '-')


def parse_cookie(header, charset='utf-8', errors='ignore'):
    """Parse a cookie.  Either from a string or WSGI environ.

    Per default encoding errors are ignore.  If you want a different behavior
    you can set `errors` to ``'replace'`` or ``'strict'``.  In strict mode a
    `HTTPUnicodeError` is raised.
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
    datetime object or a timetuple.  All times in UTC.  The `parse_date`
    function in `werkzeug.http` can be used to parse such a date.

    Outputs a string in the format ``Wdy, DD Mon YYYY HH:MM:SS GMT``.
    """
    return _dump_date(timestamp, ' ')


def redirect(location, code=302):
    """Return a response object (a WSGI application) that, if called,
    redirects the client to the target location.  Supported codes are 301,
    302, 303, 305, and 307.  300 is not supported because it's not a real
    redirect and 304 because it's the answer for a request with a request
    with defined If-Modified-Since headers.
    """
    assert code in (301, 302, 303, 305, 307)
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
    """
    new_path = environ['PATH_INFO'].strip('/') + '/'
    query_string = environ['QUERY_STRING']
    if query_string:
        new_path += '?' + query_string
    if not new_path.startswith('/'):
        new_path = '/' + new_path
    return redirect(new_path)


def responder(f):
    """Marks a function as responder.  Decorate a function with it and it
    will automatically call the return value as WSGI application.

    Example::

        @responder
        def application(environ, start_response):
            return Response('Hello World!')
    """
    return _patch_wrapper(f, lambda *a: f(*a)(*a[-2:]))


def import_string(import_name, silent=False):
    """Imports an object based on a string.  This use useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).

    If the `silent` is True the return value will be `None` if the import
    fails.

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
    it can either be a dict, MultiDict or string.

    The following options exist:

    `method`
        The request method.  Defaults to `GET`

    `input_stream`
        The input stream.  Defaults to an empty read only stream.

    `content_type`
        The content type for this request.  Default is an empty content
        type.

    `content_length`
        The value for the content length header.  Defaults to 0.

    `errors_stream`
        The wsgi.errors stream.  Defaults to `sys.stderr`.

    `multithread`
        The multithreaded flag for the WSGI Environment.  Defaults to `False`.

    `multiprocess`
        The multiprocess flag for the WSGI Environment.  Defaults to `False`.

    `run_once`
        The run_once flag for the WSGI Environment.  Defaults to `False`.
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


# create all the special key errors now that the classes are defined.
from werkzeug.exceptions import BadRequest
for _cls in MultiDict, CombinedMultiDict, Headers, EnvironHeaders:
    _cls.KeyError = BadRequest.wrap(KeyError, _cls.__name__ + '.KeyError')
del _cls, BadRequest
