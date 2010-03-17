# -*- coding: utf-8 -*-
"""
    werkzeug.debug.repr
    ~~~~~~~~~~~~~~~~~~~

    This module implements object representations for debugging purposes.
    Unlike the default repr these reprs expose a lot more information and
    produce HTML instead of ASCII.

    Together with the CSS and JavaScript files of the debugger this gives
    a colorful and more compact output.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD.
"""
import sys
import re
from traceback import format_exception_only
try:
    from collections import deque
except ImportError: # pragma: no cover
    deque = None
from werkzeug.utils import escape
from werkzeug.debug.utils import render_template


missing = object()
_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')
RegexType = type(_paragraph_re)


def debug_repr(obj):
    """Creates a debug repr of an object as HTML unicode string."""
    return DebugReprGenerator().repr(obj)


def dump(obj=missing):
    """Print the object details to stdout._write (for the interactive
    console of the web debugger.
    """
    gen = DebugReprGenerator()
    if obj is missing:
        rv = gen.dump_locals(sys._getframe(1).f_locals)
    else:
        rv = gen.dump_object(obj)
    sys.stdout._write(rv)


class _Helper(object):
    """Displays an HTML version of the normal help, for the interactive
    debugger only because it requires a patched sys.stdout.
    """

    def __call__(self, topic=None):
        title = text = None
        if topic is not None:
            import pydoc
            pydoc.help(topic)
            rv = sys.stdout.reset().decode('utf-8', 'ignore')
            paragraphs = _paragraph_re.split(rv)
            if len(paragraphs) > 1:
                title = paragraphs[0]
                text = '\n\n'.join(paragraphs[1:])
            else: # pragma: no cover
                title = 'Help'
                text = paragraphs[0]
        rv = render_template('help_command.html', title=title, text=text)
        sys.stdout._write(rv)

helper = _Helper()


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
    tuple_repr = _sequence_repr_maker('(', ')', tuple)
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
        if obj is helper:
            return helper.get_help(None)
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
        except: # pragma: no cover
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

    def dump_object(self, obj):
        repr = items = None
        if isinstance(obj, dict):
            title = 'Contents of'
            items = []
            for key, value in obj.iteritems():
                if not isinstance(key, basestring):
                    items = None
                    break
                items.append((key, self.repr(value)))
        if items is None:
            items = []
            repr = self.repr(obj)
            for key in dir(obj):
                try:
                    items.append((key, self.repr(getattr(obj, key))))
                except:
                    pass
            title = 'Details for'
        title += ' ' + object.__repr__(obj)[1:-1]
        return render_template('dump_object.html', items=items,
                               title=title, repr=repr)

    def dump_locals(self, d):
        items = [(key, self.repr(value)) for key, value in d.items()]
        return render_template('dump_object.html', items=items,
                               title='Local variables in frame', repr=None)
