# -*- coding: utf-8 -*-
"""
    werkzeug.utils
    ~~~~~~~~~~~~~~

    Various utils.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
import sys
import cgi
import urllib
import urlparse
from time import asctime, gmtime, time
from datetime import datetime
from cStringIO import StringIO
try:
    set
except NameError:
    from sets import Set as set

    def reversed(item):
        return tuple(item)[::-1]


_empty_stream = StringIO('')

_format_re = re.compile(r'\$(%s|\{%s\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))


class MultiDict(dict):
    """
    A dict that takes a list of multiple values as only argument
    in order to store multiple values per key.
    """

    def __init__(self, mapping=()):
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
        """
        Return the first data value for this key;
        raises KeyError if not found.
        """
        return dict.__getitem__(self, key)[0]

    def __setitem__(self, key, value):
        """Set an item as list."""
        dict.__setitem__(self, key, [value])

    def get(self, key, default=None, type=None):
        """
        Return the default value if the requested data doesn't exist.
        Additionally you can pass it a type function that is used as
        converter.  That function should either conver the value or
        raise a `ValueError`.
        """
        try:
            rv = self[key]
            if type is not None:
                rv = type(rv)
        except (KeyError, ValueError):
            rv = default
        return rv

    def getlist(self, key, type=None):
        """Return an empty list if the requested data doesn't exist"""
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

    def to_dict(self, flat=True):
        """
        Returns the contents as simple dict.  If `flat` is `True` the
        resulting dict will only have the first item present, if `flat`
        is `False` all values will be lists.
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

    def get(self, key, default=None, type=None):
        for d in self.dicts:
            if key in d:
                if type is not None:
                    try:
                        type(d[key])
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
        """
        Returns the contents as simple dict.  If `flat` is `True` the
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
    """
    Represents an uploaded file.
    """

    def __init__(self, name, filename, content_type, content_length, stream):
        self.name = name
        self.filename = filename
        self.content_type = content_type
        self.content_length = content_length
        self.stream = stream

    def save(self, dst, buffer_size=16384):
        """
        Save the file to a destination path or file object.  If the
        destination is a file object you have to close it yourself after the call.
        The buffer size is the number of bytes held in the memory during the copy
        process.  It defaults to 16KB.
        """
        from shutil import copyfileobj
        if isinstance(dst, basestring):
            dst = file(dst, 'wb')
            close_dst = True
        else:
            close_dst = False

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
    An object that stores some headers.  It has a dict like interface
    but is ordered and can store keys multiple times.
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
            self._list[:] = defaults

    def __getitem__(self, key):
        ikey = key.lower()
        for k, v in self._list:
            if k.lower() == ikey:
                return v
        raise KeyError(key)

    def __eq__(self, other):
        return other.__class__ is self.__class__ and \
               set(other._list) == set(self._list)

    def __ne__(self, other):
        return not self.__eq__(other)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key):
        ikey = key.lower()
        result = []
        for k, v in self:
            if k.lower() == ikey:
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

    def extend(self, seq):
        for key, value in seq:
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
        try:
            self[key]
        except KeyError:
            return False
        return True

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
        self.remove(key)
        self.add(key, value)

    __setitem__ = set

    def to_list(self, charset='utf-8'):
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

    def __copy__(self):
        return self.copy()

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            list(self)
        )


class EnvironHeaders(Headers):
    """
    Read only version of the headers from wsgi environment.
    """

    def __init__(self, environ):
        self.environ = environ

    def __eq__(self, other):
        return self is other

    def __getitem__(self, key):
        return self.environ['HTTP_' + key.upper().replace('-', '_')]

    def __iter__(self):
        for key, value in self.environ.iteritems():
            if key.startswith('HTTP_'):
                yield key[5:].replace('_', '-').title(), value

    def copy(self):
        raise TypeError('cannot create %r copies' % self.__class__.__name__)

    def _immutable(self, *a, **kw):
        raise TypeError('%r is immutable' % self.__class__.__name__)
    remove = __delitem__ = add = clear = extend = set = __setitem__ = \
        _immutable
    del _immutable


class SharedDataMiddleware(object):
    """
    Redirects calls to an folder with static data.
    """

    def __init__(self, app, exports, disallow=None):
        self.app = app
        self.exports = exports
        self.disallow = disallow

    def serve_file(self, filename, start_response):
        from mimetypes import guess_type
        guessed_type = guess_type(filename)
        mime_type = guessed_type[0] or 'text/plain'
        expiry = asctime(gmtime(time() + 3600))
        start_response('200 OK', [('Content-Type', mime_type),
                                  ('Cache-Control', 'public'),
                                  ('Expires', expiry)])
        fp = file(filename, 'rb')
        try:
            return [fp.read()]
        finally:
            fp.close()

    def __call__(self, environ, start_response):
        cleaned_path = environ.get('PATH_INFO', '').strip('/')
        for sep in os.sep, os.altsep:
            if sep and sep != '/':
                cleaned_path = cleaned_path.replace(sep, '/')
        path = '/'.join([''] + [x for x in cleaned_path.split('/')
                                if x and x != '..'])
        for search_path, file_path in self.exports.iteritems():
            if search_path == path and os.path.isfile(file_path):
                return self.serve_file(file_path, start_response)
            if not search_path.endswith('/'):
                search_path += '/'
            if path.startswith(search_path):
                real_path = os.path.join(file_path, path[len(search_path):])
                if os.path.exists(real_path) and os.path.isfile(real_path):
                    if self.disallow:
                        from fnmatch import fnmatch
                        for pattern in self.disallow:
                            if fnmatch(real_path, pattern):
                                break
                        else:
                            return self.serve_file(real_path, start_response)
                    else:
                        return self.serve_file(real_path, start_response)
        return self.app(environ, start_response)


class DispatcherMiddleware(object):
    """
    Allows one to mount middlewares or application in a WSGI application.
    This is useful if you want to combine multiple WSGI applications.
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
            script = items[:-1].join('/')
            path_info = '/%s%s' % (items[-1], path_info)
        else:
            app = self.mapping.get(script, self.app)
        original_script_name = environ.get('SCRIPT_NAME', '')
        environ['SCRIPT_NAME'] = original_script_name + script_name
        environ['PATH_INFO'] = path_info
        return app(environ, start_response)


class ClosingIterator(object):
    """
    A class that wraps an iterator (which can have a close method) and
    adds a close method for the callback and the iterator.

    Usage::

        return ClosingIterator(iter, [list, of, callbacks])
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


class cached_property(object):
    """
    Descriptor implementing a "lazy property", i.e. the function
    calculating the property value is called only once.
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


def lazy_property(func, name=None, doc=None):
    """Backwards compatibility interface."""
    from warnings import warn
    warn(DeprecationWarning('lazy_property is now called cached_property '
                            'because it reflects the purpose better.  With '
                            'Werkzeug 0.3 the old name will be unavailable'))
    return cached_property(func, name, doc)


class environ_property(object):
    """
    Maps request attributes to environment variables. This works not only
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

    def __init__(self, name, default=None, convert=None, read_only=False,
                 doc=None):
        self.name = name
        self.default = default
        self.convert = convert
        self.read_only = read_only
        self.__doc__ = doc

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        rv = obj.environ.get(self.name, self.default)
        if rv is self.default or self.convert is None:
            return rv
        try:
            return self.convert(rv)
        except (ValueError, TypeError):
            return self.default

    def __set__(self, obj, value):
        if self.read_only:
            raise AttributeError('read only property')
        obj.environ[self.name] = value

    def __delete__(self, obj):
        if self.read_only:
            raise AttributeError('read only property')
        obj.environ.pop(self.name, None)

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.name
        )


def format_string(string, context):
    """
    String-template format a string::

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


def url_decode(s, charset='utf-8', decode_keys=False):
    """
    Parse a querystring and return it as `MultiDict`.
    """
    tmp = []
    for key, values in cgi.parse_qs(str(s)).iteritems():
        for value in values:
            if decode_keys:
                key = key.decode(charset, 'ignore')
            tmp.append((key, value.decode(charset, 'ignore')))
    return MultiDict(tmp)


def url_encode(obj, charset='utf-8', encode_keys=False):
    """Urlencode a dict/MultiDict."""
    if obj is None:
        items = []
    elif isinstance(obj, MultiDict):
        items = obj.lists()
    elif isinstance(obj, dict):
        items = [(key, [value]) for key, value in obj.iteritems()]
    else:
        items = obj
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


def url_quote(s, charset='utf-8'):
    """
    URL encode a single string with a given encoding.
    """
    if isinstance(s, unicode):
        s = s.encode(charset)
    return urllib.quote(s)


def url_quote_plus(s, charset='utf-8'):
    """
    URL encode a single string with the given encoding and convert
    whitespace to "+".
    """
    if isinstance(s, unicode):
        s = s.encode(charset)
    return urllib.quote_plus(s)


def url_unquote(s, charset='utf-8'):
    """
    URL decode a single string with a given decoding.
    """
    return urllib.unquote(s).decode(charset, 'ignore')


def url_unquote_plus(s, charset='utf-8'):
    """
    URL decode a single string with the given decoding and decode
    a "+" to whitespace.
    """
    return urllib.unquote_plus(s).decode(charset, 'ignore')


escape = cgi.escape


def get_host(environ):
    """
    Return the real host for the given environment.
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
    """
    Recreate the URL of the current request.
    """
    tmp = [environ['wsgi.url_scheme'], '://']
    cat = tmp.append
    cat(get_host(environ))

    if host_only:
        return ''.join(tmp) + '/'

    cat(urllib.quote(environ.get('SCRIPT_NAME', '').rstrip('/')))
    if root_only:
        cat('/')
    else:
        cat(urllib.quote('/' + environ.get('PATH_INFO', '') \
                  .lstrip('/')))

        if not strip_querystring:
            qs = environ.get('QUERY_STRING')
            if qs:
                cat('?' + qs)

    return ''.join(tmp)


def cookie_date(expires, _date_delim='-'):
    """
    Formats the time to ensure compatibility with Netscape's cookie standard.

    Accepts a floating point number expressed in seconds since the epoc in, a
    datetime object or a timetuple.  All times in UTC.

    Outputs a string in the format 'Wdy, DD-Mon-YYYY HH:MM:SS GMT'.
    """
    if isinstance(expires, datetime):
        expires = expires.utctimetuple()
    elif isinstance(expires, (int, long, float)):
        expires = gmtime(expires)

    return '%s, %02d%s%s%s%s %02d:%02d:%02d GMT' % (
        ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[expires.tm_wday],
        expires.tm_mday,
        _date_delim,
        ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
         'Oct', 'Nov', 'Dec')[expires.tm_mon - 1],
        _date_delim,
        str(expires.tm_year),
        expires.tm_hour,
        expires.tm_min,
        expires.tm_sec
    )


def http_date(timestamp):
    """
    Formats the time to match the RFC1123 date format.

    Accepts a floating point number expressed in seconds since the epoc in, a
    datetime object or a timetuple.  All times in UTC.

    Outputs a string in the format 'Wdy, DD Mon YYYY HH:MM:SS GMT'.
    """
    return cookie_date(timestamp, ' ')


def redirect(location, code=302):
    """
    Return a response object (a WSGI application) that, if called, redirects
    the client to the target location.  Supported codes are 301, 302, 303,
    305, and 307.  300 is not supported because it's not a real redirect and
    304 because it's the answer for a request with a request with defined
    If-Modified-Since headers.
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
    """
    Redirect to the same URL but with a slash appended.  The behavior
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
    """
    Marks a function as responder.  Decorate a function with it and it
    will automatically call the return value as WSGI application.

    Example::

        @responder
        def application(environ, start_response):
            return Response('Hello World!')
    """
    def wrapper(environ, start_response):
        return f(environ, start_response)(environ, start_response)
    try:
        wrapper.__name__ = f.__name__
        wrapper.__module__ = f.__module__
        wrapper.__doc__ = f.__doc__
    except:
        pass
    return wrapper


def import_string(import_name):
    """Import an object or module from a string."""
    if ':' in import_name:
        module, obj = import_name.split(':', 1)
    elif '.' in import_name:
        items = import_name.split('.')
        module = '.'.join(items[:-1])
        obj = items[-1]
    else:
        return __import__(import_name)
    return getattr(__import__(module, None, None, [obj]), obj)


def create_environ(path='/', base_url=None, query_string=None, method='GET',
                   input_stream=None, content_type=None, content_length=0,
                   errors_stream=None, multithread=False,
                   multiprocess=False, run_once=False):
    """
    Create a new WSGI environ dict based on the values passed.  The first
    parameter should be the path of the request which defaults to '/'.
    The second one can either be a absolute path (in that case the url
    host is localhost:80) or a full path to the request with scheme,
    netloc port and the path to the script.
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
    """
    Return a tuple in the form (app_iter, status, headers) of the application
    output.  This works best if you pass it an application that returns a
    generator all the time.

    Sometimes applications may use the `write()` callable returned
    by the `start_response` function.  This tries to resolve such edge
    cases automatically.  But if you don't get the expected output you
    should set `buffered` to `True` which enforces buffering.
    """
    # TODO: only read until a response is set, then return a closing
    # iterator that yields the buffer first and then the data.
    response = []
    buffer = []

    def start_response(status, headers, exc_info=None):
        if exc_info is not None:
            raise exc_info[0], exc_info[1], exc_info[2]
        response[:] = [status, headers]
        return buffer.append

    app_iter = app(environ, start_response)

    if buffered or buffer or not response:
        try:
            buffer.extend(app_iter)
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()
        app_iter = buffer

    return app_iter, response[0], response[1]
