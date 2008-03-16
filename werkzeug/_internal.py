# -*- coding: utf-8 -*-
"""
    werkzeug._internal
    ~~~~~~~~~~~~~~~~~~

    This module provides internally used helpers and constants.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import cgi
from cStringIO import StringIO
from Cookie import BaseCookie, Morsel, CookieError
from time import asctime, gmtime, time
from datetime import datetime


_logger = None
_empty_stream = StringIO('')


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
    226:    'IM Used',              # see RFC 3229
    300:    'Multiple Choices',
    301:    'Moved Permanently',
    302:    'Found',
    303:    'See Other',
    304:    'Not Modified',
    305:    'Use Proxy',
    307:    'Temporary Redirect',
    400:    'Bad Request',
    401:    'Unauthorized',
    402:    'Payment Required',     # unused
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
    449:    'Retry With',           # propritary MS extension
    500:    'Internal Server Error',
    501:    'Not Implemented',
    502:    'Bad Gateway',
    503:    'Service Unavailable',
    504:    'Gateway Timeout',
    505:    'HTTP Version Not Supported',
    507:    'Insufficient Storage',
    510:    'Not Extended'
}


def _log(type, message, *args, **kwargs):
    """
    Log into the internal werkzeug logger.

    :internal:
    """
    global _logger
    if _logger is None:
        import logging
        handler = logging.StreamHandler()
        _logger = logging.getLogger('werkzeug')
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
    getattr(_logger, type)(message.rstrip(), *args, **kwargs)


def _patch_wrapper(old, new):
    """
    Helper function that forwards all the function details to the
    decorated function.
    """
    try:
        new.__name__ = old.__name__
        new.__module__ = old.__module__
        new.__doc__ = old.__doc__
        new.__dict__ = old.__dict__
    except AttributeError:
        pass
    return new


def _decode_unicode(value, charset, errors):
    """
    Like the regular decode function but this one raises an
    `HTTPUnicodeError` if errors is `strict`.
    """
    fallback = None
    if errors.startswith('fallback:'):
        fallback = errors[9:]
        errors = 'strict'
    try:
        return value.decode(charset, errors)
    except UnicodeError, e:
        if fallback is not None:
            return value.decode(fallback, 'ignore')
        from werkzeug.exceptions import HTTPUnicodeError
        raise HTTPUnicodeError(str(e))


def _iter_modules(path):
    import pkgutil
    if hasattr(pkgutil, 'iter_modules'):
        for importer, modname, ispkg in pkgutil.iter_modules(path):
            yield modname, ispkg
        return
    from inspect import getmodulename
    from pydoc import ispackage
    found = set()
    for path in path:
        for filename in os.listdir(path):
            p = os.path.join(path, filename)
            modname = getmodulename(filename)
            if modname and modname != '__init__':
                if modname not in found:
                    found.add(modname)
                    yield modname, ispackage(modname)


def _dump_date(d, delim):
    if d is None:
        d = gmtime()
    elif isinstance(d, datetime):
        d = d.utctimetuple()
    elif isinstance(d, (int, long, float)):
        d = gmtime(d)
    return '%s, %02d%s%s%s%s %02d:%02d:%02d GMT' % (
        ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[d.tm_wday],
        d.tm_mday, delim,
        ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
         'Oct', 'Nov', 'Dec')[d.tm_mon - 1],
        delim, str(d.tm_year), d.tm_hour, d.tm_min, d.tm_sec
    )


class _ExtendedMorsel(Morsel):
    _reserved = {'httponly': 'HttpOnly'}
    _reserved.update(Morsel._reserved)

    def __init__(self, name=None, value=None):
        Morsel.__init__(self)
        if name is not None:
            self.set(name, value, value)

    def OutputString(self, attrs=None):
        httponly = self.pop('httponly', False)
        result = Morsel.OutputString(self, attrs).rstrip('\t ;')
        if httponly:
            result += '; HttpOnly'
        return result


class _StorageHelper(cgi.FieldStorage):
    """
    Helper class used by `parse_form_data` to parse submitted file and
    form data.  Don't use this class directly.  This also defines a simple
    repr that prints just the filename as the default repr reads the
    complete data of the stream.
    """

    FieldStorageClass = cgi.FieldStorage

    def __init__(self, environ, stream_factory):
        if stream_factory is not None:
            self.make_file = lambda binary=None: stream_factory()
        cgi.FieldStorage.__init__(self,
            fp=environ['wsgi.input'],
            environ={
                'REQUEST_METHOD':   environ['REQUEST_METHOD'],
                'CONTENT_TYPE':     environ['CONTENT_TYPE'],
                'CONTENT_LENGTH':   environ['CONTENT_LENGTH']
            },
            keep_blank_values=True
        )

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


class _ExtendedCookie(BaseCookie):
    """
    Form of the base cookie that doesn't raise a `CookieError` for
    malformed keys.  This has the advantage that broken cookies submitted
    by nonstandard browsers don't cause the cookie to be empty.
    """

    def _BaseCookie__set(self, key, real_value, coded_value):
        morsel = self.get(key, _ExtendedMorsel())
        try:
            morsel.set(key, real_value, coded_value)
        except CookieError:
            pass
        dict.__setitem__(self, key, morsel)


class _DictAccessorProperty(object):
    """
    Baseclass for `environ_property` and `header_property`.
    """

    def __init__(self, name, default=None, load_func=None, dump_func=None,
                 read_only=False, doc=None):
        self.name = name
        self.default = default
        self.load_func = load_func
        self.dump_func = dump_func
        self.read_only = read_only
        self.__doc__ = doc

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        storage = self.lookup(obj)
        if self.name not in storage:
            return self.default
        rv = storage[self.name]
        if self.load_func is not None:
            try:
                rv = self.load_func(rv)
            except (ValueError, TypeError):
                rv = self.default
        return rv

    def __set__(self, obj, value):
        if self.read_only:
            raise AttributeError('read only property')
        if self.dump_func is not None:
            value = self.dump_func(value)
        self.lookup(obj)[self.name] = value

    def __delete__(self, obj):
        if self.read_only:
            raise AttributeError('read only property')
        self.lookup(obj).pop(self.name, None)

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.name
        )


class _UpdateDict(dict):
    """
    A dict that calls `on_update` on modifications.
    """

    def __init__(self, data, on_update):
        dict.__init__(self, data)
        self.on_update = on_update

    def calls_update(f):
        def oncall(self, *args, **kw):
            rv = f(self, *args, **kw)
            if self.on_update is not None:
                self.on_update(self)
            return rv
        return _patch_wrapper(f, oncall)

    __setitem__ = calls_update(dict.__setitem__)
    __delitem__ = calls_update(dict.__delitem__)
    clear = calls_update(dict.clear)
    pop = calls_update(dict.pop)
    popitem = calls_update(dict.popitem)
    setdefault = calls_update(dict.setdefault)
    update = calls_update(dict.update)
