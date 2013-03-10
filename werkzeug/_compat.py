
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import six

iterkeys = lambda d, *a, **kw: getattr(d, six._iterkeys)(*a, **kw)
itervalues = lambda d, *a, **kw: getattr(d, six._itervalues)(*a, **kw)
iteritems = lambda d, *a, **kw: getattr(d, six._iteritems)(*a, **kw)
