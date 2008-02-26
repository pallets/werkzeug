# -*- coding: utf-8 -*-
"""
    werkzeug.debug.repr
    ~~~~~~~~~~~~~~~~~~~

    This module implements object representations for debugging purposes.
    Unlike the default repr these reprs expose a lot more information and
    produce HTML instead of ASCII.

    Together with the CSS and JavaScript files of the debugger this gives
    a colorful and more compact output.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
import sys
import re
from traceback import format_exception_only
try:
    from collections import deque
except ImportError:
    deque = None
from cgi import escape
try:
    set
except NameError:
    from sets import Set as set, ImmutableSet as frozenset


RegexType = type(re.compile(''))


def _add_subclass_info(inner, obj, base):
    if isinstance(base, tuple):
        for base in base:
            if type(obj) is base:
                return inner
    elif type(obj) is base:
        return inner
    module = ''
    if obj.__class__.__module__ not in ('__builtin__', 'exceptions'):
        module = '<span class="module">%s.</span>' % obj.__class__.__module__
    return '%s%s(%s)' % (module, obj.__class__.__name__, inner)


def _sequence_repr_maker(left, right, base=object(), limit=5):
    def proxy(obj):
        buf = [left]
        have_extended_section = False
        for idx, item in enumerate(obj):
            if idx:
                buf.append(', ')
            if idx == limit - 1:
                buf.append('<span class="extended">')
                have_extended_section = True
            buf.append(debug_repr(item))
        if have_extended_section:
            buf.append('</span>')
        buf.append(right)
        return _add_subclass_info(u''.join(buf), obj, base)
    return proxy


list_repr = _sequence_repr_maker('[', ']', list)
tuple_repr = _sequence_repr_maker('[', ']', tuple)
dict_repr = _sequence_repr_maker('[', ']', dict)
set_repr = _sequence_repr_maker('set([', '])', set)
frozenset_repr = _sequence_repr_maker('frozenset([', '])', frozenset)

if deque is not None:
    deque_repr = _sequence_repr_maker('<span class="module">collections.'
                                      '</span>deque([', '])', deque)


def regex_repr(obj):
    pattern = repr(obj.pattern).decode('string-escape', 'ignore')
    if pattern[:1] == 'u':
        pattern = 'ur' + pattern[1:]
    else:
        pattern = 'r' + pattern
    return u're.compile(<span class="string regex">%s</span>)' % pattern


def string_repr(obj, limit=70):
    buf = ['<span class="string">']
    escaped = escape(obj)
    a = repr(escaped[:limit])
    b = repr(escaped[limit:])
    if isinstance(obj, unicode):
        buf.append('u')
        a = a[1:]
        b = b[1:]
    if b != "''":
        buf.extend((a[:-1], '<span class="extended">', b[1:], '</span>'))
    else:
        buf.append(a)
    buf.append('</span>')
    return _add_subclass_info(u''.join(buf), obj, (str, unicode))


def dict_repr(d, limit=5):
    buf = ['{']
    have_extended_section = False
    for idx, (key, value) in enumerate(d.iteritems()):
        if idx:
            buf.append(', ')
        if idx == limit - 1:
            buf.append('<span class="extended">')
            have_extended_section = True
        buf.append('<span class="pair"><span class="key">%s</span>: '
                   '<span class="value">%s</span></span>' % (debug_repr(key),
                                                             debug_repr(value)))
    if have_extended_section:
        buf.append('</span>')
    buf.append('}')
    return _add_subclass_info(u''.join(buf), d, dict)


def object_repr(obj, limit=80):
    rv = repr(obj).decode('utf-8', 'replace')
    try:
        debug_info = '<span class="extended">%s</span>' % dict_repr(obj.__dict__)
    except:
        debug_info = ''
    if rv[-1:] in '>)]}':
        rv = escape(rv[:-1]) + ' ' + debug_info + escape(rv[-1])
    else:
        rv = escape(rv) + debug_info
    return u'<span class="object">%s</span>' % rv


def debug_repr(obj):
    try:
        if isinstance(obj, (int, long, float, complex)):
            return u'<span class="number">%r</span>' % obj
        if isinstance(obj, basestring):
            return string_repr(obj)
        if isinstance(obj, RegexType):
            return regex_repr(obj)
        if isinstance(obj, list):
            return list_repr(obj)
        if isinstance(obj, tuple):
            return tuple_repr(obj)
        if isinstance(obj, set):
            return set_repr(obj)
        if isinstance(obj, frozenset):
            return frozenset_repr(obj)
        if isinstance(obj, dict):
            return dict_repr(obj)
        if deque is not None and isinstance(obj, deque):
            return deque_repr(obj)
        return object_repr(obj)
    except:
        try:
            info = ''.join(format_exception_only(*sys.exc_info()[:2]))
        except:
            info = '?'
        return u'<span class="brokenrepr">&lt;broken repr (%s)&gt;' \
               u'</span>' % escape(info.decode('utf-8', 'ignore').strip())
