import sys

from . import _urlparse as urlparse

import six

def iterkeys(d, *a, **kw):
    return iter(getattr(d, six._iterkeys)(*a, **kw))

def itervalues(d, *a, **kw):
    return iter(getattr(d, six._itervalues)(*a, **kw))

def iteritems(d, *a, **kw):
    return iter(getattr(d, six._iteritems)(*a, **kw))

if six.PY3:
    _iterlists = 'lists'
    _iterlistvalues = 'listvalues'
else:
    _iterlists = 'iterlists'
    _iterlistvalues = 'iterlistvalues'

def iterlists(d, *a, **kw):
    return getattr(d, _iterlists)(*a, **kw)

def iterlistvalues(d, *a, **kw):
    return getattr(d, _iterlistvalues)(*a, **kw)

try:
    unichr = unichr # py2
except NameError:
    unichr = chr # py3

def to_unicode(x, charset):
    '''please use carefully'''
    if x is None:
        return None
    if isinstance(x, six.text_type):
        return x
    return x.decode(charset)

def to_bytes(x, charset):
    '''please use carefully'''
    if x is None:
        return None
    if six.PY3:
        if not isinstance(x, bytes):
            x = str(x).encode(charset)
        return x
    if isinstance(x, unicode):
        return x.encode(charset)
    return str(x)

def to_native(x, charset=sys.getdefaultencoding()):
    '''please use carefully'''
    if x is None or isinstance(x, str):
        return x
    if six.PY3:
        return x.decode(charset)
    else:
        return x.encode(charset)

def string_join(iterable, default=''):
    '''concatenate any string type'''
    l = list(iterable)
    if l:
        if isinstance(l[0], bytes):
            return b''.join(l)
        return u''.join(l)
    return default
