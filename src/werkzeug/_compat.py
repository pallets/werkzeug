# flake8: noqa
# This whole file is full of lint errors
import functools
import operator
import sys
import collections.abc as collections_abc
from io import StringIO, BytesIO

try:
    import builtins
except ImportError:
    import __builtin__ as builtins


WIN = sys.platform.startswith("win")

_identity = lambda x: x


unichr = chr
text_type = str
string_types = (str,)
integer_types = (int,)

iterkeys = lambda d, *args, **kwargs: iter(d.keys(*args, **kwargs))
itervalues = lambda d, *args, **kwargs: iter(d.values(*args, **kwargs))
iteritems = lambda d, *args, **kwargs: iter(d.items(*args, **kwargs))

iterlists = lambda d, *args, **kwargs: iter(d.lists(*args, **kwargs))
iterlistvalues = lambda d, *args, **kwargs: iter(d.listvalues(*args, **kwargs))

int_to_byte = operator.methodcaller("to_bytes", 1, "big")
iter_bytes = functools.partial(map, int_to_byte)

def reraise(tp, value, tb=None):
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value

fix_tuple_repr = _identity
implements_iterator = _identity
implements_to_string = _identity
implements_bool = _identity
native_string_result = _identity
imap = map
izip = zip
ifilter = filter
range_type = range

NativeStringIO = StringIO

_latin1_encode = operator.methodcaller("encode", "latin1")

def make_literal_wrapper(reference):
    if isinstance(reference, text_type):
        return _identity
    return _latin1_encode

def normalize_string_tuple(tup):
    """
    Ensures that all types in the tuple are either strings
    or bytes.
    """
    tupiter = iter(tup)
    is_text = isinstance(next(tupiter, None), text_type)
    for arg in tupiter:
        if isinstance(arg, text_type) != is_text:
            raise TypeError(
                "Cannot mix str and bytes arguments (got %s)" % repr(tup)
            )
    return tup

try_coerce_native = _identity
wsgi_get_bytes = _latin1_encode

def wsgi_decoding_dance(s, charset="utf-8", errors="replace"):
    return s.encode("latin1").decode(charset, errors)

def wsgi_encoding_dance(s, charset="utf-8", errors="replace"):
    if isinstance(s, text_type):
        s = s.encode(charset)
    return s.decode("latin1", errors)

def to_bytes(x, charset=sys.getdefaultencoding(), errors="strict"):
    if x is None:
        return None
    if isinstance(x, (bytes, bytearray, memoryview)):  # noqa
        return bytes(x)
    if isinstance(x, str):
        return x.encode(charset, errors)
    raise TypeError("Expected bytes")

def to_native(x, charset=sys.getdefaultencoding(), errors="strict"):
    if x is None or isinstance(x, str):
        return x
    return x.decode(charset, errors)


def to_unicode(
    x, charset=sys.getdefaultencoding(), errors="strict", allow_none_charset=False
):
    if x is None:
        return None
    if not isinstance(x, bytes):
        return text_type(x)
    if charset is None and allow_none_charset:
        return x
    return x.decode(charset, errors)
