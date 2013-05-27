import sys
import operator
try:
    import builtins
except ImportError:
    import __builtin__ as builtins


PY2 = sys.version_info[0] == 2

_identity = lambda x: x

if PY2:
    unichr = unichr
    text_type = unicode
    string_types = (str, unicode)
    integer_types = (int, long)

    iterkeys = lambda d, *args, **kwargs: d.iterkeys(*args, **kwargs)
    itervalues = lambda d, *args, **kwargs: d.itervalues(*args, **kwargs)
    iteritems = lambda d, *args, **kwargs: d.iteritems(*args, **kwargs)

    iterlists = lambda d, *args, **kwargs: d.iterlists(*args, **kwargs)
    iterlistvalues = lambda d, *args, **kwargs: d.iterlistvalues(*args, **kwargs)
    int_to_byte = chr

    exec('def reraise(tp, value, tb=None):\n raise tp, value, tb')

    def implements_iterator(cls):
        cls.next = cls.__next__
        del cls.__next__
        return cls

    def implements_to_string(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode('utf-8')
        return cls

    def implements_bool(cls):
        cls.__nonzero__ = cls.__bool__
        del cls.__bool__
        return cls

    from itertools import imap, izip, ifilter
    xrange = xrange

    from StringIO import StringIO, StringIO as BytesIO
    NativeStringIO = BytesIO
else:
    unichr = chr
    text_type = str
    string_types = (str, )
    integer_types = (int, )

    iterkeys = lambda d, *args, **kwargs: iter(d.keys(*args, **kwargs))
    itervalues = lambda d, *args, **kwargs: iter(d.values(*args, **kwargs))
    iteritems = lambda d, *args, **kwargs: iter(d.items(*args, **kwargs))

    iterlists = lambda d, *args, **kwargs: iter(d.lists(*args, **kwargs))
    iterlistvalues = lambda d, *args, **kwargs: iter(d.listvalues(*args, **kwargs))

    int_to_byte = operator.methodcaller('to_bytes', 1, 'big')

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

    implements_iterator = _identity
    implements_to_string = _identity
    implements_bool = _identity
    imap = map
    izip = zip
    ifilter = filter
    xrange = range

    from io import StringIO, BytesIO
    NativeStringIO = StringIO


def to_unicode(x, charset=sys.getdefaultencoding()):
    """please use carefully"""
    if x is None:
        return None
    if not isinstance(x, bytes):
        return text_type(x)
    return x.decode(charset)


def to_bytes(x, charset=sys.getdefaultencoding()):
    """please use carefully"""
    if x is None:
        return None
    if PY2:
        if isinstance(x, unicode):
            return x.encode(charset)
        return str(x)
    else:
        if not isinstance(x, bytes):
            x = str(x).encode(charset)
        return x


def to_native(x, charset=sys.getdefaultencoding(), errors="strict"):
    """please use carefully"""
    if x is None or isinstance(x, str):
        return x
    if PY2:
        return x.encode(charset, errors)
    else:
        return x.decode(charset, errors)


def string_join(iterable, default=""):
    """concatenate any string type"""
    l = list(iterable)
    if l:
        if isinstance(l[0], bytes):
            return b"".join(l)
        return u"".join(l)
    return default


def iter_bytes_as_bytes(iterable):
    # XXX: optimize
    return ((int_to_byte(x) if isinstance(x, int) else x) for x in iterable)


def coerce_string(string, reference):
    """Coerces a native string into the reference string type.."""
    assert isinstance(string, str), 'Given string is not a native string'
    reference_type = type(reference)
    if not isinstance(string, reference_type) and reference_type is bytes:
        string = string.encode('ascii')
    return string


def normalize_string_tuple(tup):
    """Normalizes a string tuple to a common type.  As by Python 2
    rules upgrades to unicode are implicit.
    """
    if any(isinstance(x, text_type) for x in tup):
        return tuple(to_unicode(x) for x in tup)
    return tup
