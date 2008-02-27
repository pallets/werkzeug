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


def debug_repr(obj):
    """Creates a debug repr of an object as HTML unicode string."""
    return DebugReprGenerator().repr(obj)


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


class DebugReprGenerator(object):

    def __init__(self):
        self._stack = []

    def _sequence_repr_maker(left, right, base=object(), limit=8):
        def proxy(self, obj, recursive):
            if recursive:
                return _add_subclass_info(left + '...' + right, obj, base)
            buf = [left]
            have_extended_section = False
            for idx, item in enumerate(obj):
                if idx:
                    buf.append(', ')
                if idx == limit:
                    buf.append('<span class="extended">')
                    have_extended_section = True
                buf.append(self.repr(item))
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
    del _sequence_repr_maker

    def regex_repr(self, obj):
        pattern = repr(obj.pattern).decode('string-escape', 'ignore')
        if pattern[:1] == 'u':
            pattern = 'ur' + pattern[1:]
        else:
            pattern = 'r' + pattern
        return u're.compile(<span class="string regex">%s</span>)' % pattern

    def string_repr(self, obj, limit=70):
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

    def dict_repr(self, d, recursive, limit=5):
        if recursive:
            return _add_subclass_info(u'{...}', d, dict)
        buf = ['{']
        have_extended_section = False
        for idx, (key, value) in enumerate(d.iteritems()):
            if idx:
                buf.append(', ')
            if idx == limit - 1:
                buf.append('<span class="extended">')
                have_extended_section = True
            buf.append('<span class="pair"><span class="key">%s</span>: '
                       '<span class="value">%s</span></span>' %
                       (self.repr(key), self.repr(value)))
        if have_extended_section:
            buf.append('</span>')
        buf.append('}')
        return _add_subclass_info(u''.join(buf), d, dict)

    def object_repr(self, obj):
        return u'<span class="object">%s</span>' % \
               escape(repr(obj).decode('utf-8', 'replace'))

    def dispatch_repr(self, obj, recursive):
        if isinstance(obj, (int, long, float, complex)):
            return u'<span class="number">%r</span>' % obj
        if isinstance(obj, basestring):
            return self.string_repr(obj)
        if isinstance(obj, RegexType):
            return self.regex_repr(obj)
        if isinstance(obj, list):
            return self.list_repr(obj, recursive)
        if isinstance(obj, tuple):
            return self.tuple_repr(obj, recursive)
        if isinstance(obj, set):
            return self.set_repr(obj, recursive)
        if isinstance(obj, frozenset):
            return self.frozenset_repr(obj, recursive)
        if isinstance(obj, dict):
            return self.dict_repr(obj, recursive)
        if deque is not None and isinstance(obj, deque):
            return self.deque_repr(obj, recursive)
        return self.object_repr(obj)

    def fallback_repr(self):
        try:
            info = ''.join(format_exception_only(*sys.exc_info()[:2]))
        except:
            info = '?'
        return u'<span class="brokenrepr">&lt;broken repr (%s)&gt;' \
               u'</span>' % escape(info.decode('utf-8', 'ignore').strip())

    def repr(self, obj):
        recursive = False
        for item in self._stack:
            if item is obj:
                recursive = True
                break
        self._stack.append(obj)
        try:
            try:
                return self.dispatch_repr(obj, recursive)
            except:
                return self.fallback_repr()
        finally:
            self._stack.pop()
