
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import six
from functools import partial

def iterkeys(d, *a, **kw):
    return iter(getattr(d, six._iterkeys)(*a, **kw))

def itervalues(d, *a, **kw):
    return iter(getattr(d, six._itervalues)(*a, **kw))

def iteritems(d, *a, **kw):
    return iter(getattr(d, six._iteritems)(*a, **kw))

dict_iterkeys = partial(iterkeys, dict)
dict_itervalues = partial(itervalues, dict)
dict_iteritems = partial(iteritems, dict)

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
