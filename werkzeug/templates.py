# -*- coding: utf-8 -*-
r"""
    werkzeug.templates
    ~~~~~~~~~~~~~~~~~~

    A very simple Python "Template Engine". In fact it just recognizes
    PHP like blocks and executes the code in them::

        t = Template('<% for u in users %>${u['username']}\n<% endfor %>')
        t.render(users=[{'username': 'John'},
                        {'username': 'Jane'}])

    would result in::

        John
        Jane

    The syntax elements are a mixture of django, genshi text and mod_python
    templates and used internally in werkzeug components.

    We do not recommend using this template engine in a real environment
    because is quite slow and does not provide any advanced features.  For
    simple applications (cgi script like) this can however be sufficient.

    Syntax Elements
    ---------------

    Printing Variables::

        ${expression} or <%py print expression %>

    For Loops::

        <% for item in seq %>
            ...
        <% endfor %>

    While Loops::

        <% while expression %>
            <% break / continue %>
        <% endwhile %>

    If Conditions::

        <% if expression %>
            ...
        <% elif expression %>
            ...
        <% else %>
            ...
        <% endif %>

    Python Expressions::

        <%py
            ...
        %>

        <%python
            ...
        %>

    Note on python expressions:  You cannot start a loop in a python block
    and continue it in another one.  This example does *not* work::

        <%python
            for item in seq:
        %>
            ...

    Missing Variables
    -----------------

    If you try to access a missing variable you will get back an `Undefined`
    object.  You can iterate over such an object or print it and it won't
    fail.  However every other operation will raise an error.  To test if a
    variable is undefined you can use this expression::

        <% if variable is Undefined %>
            ...
        <% endif %>


    XXX: the parse_data method uses code from the genshi template engine
         (genshi.template.eval).  Figure out correct copyright information
         before release.

    :copyright: 2006 by Armin Ronacher.
    :license: BSD License.
"""
import sys
import re
from compiler import ast, parse
from compiler.pycodegen import ModuleCodeGenerator
from tokenize import tokenprog
from werkzeug import utils


directive_re = re.compile(r'(?<!\\)<%(?:(#)|(py(?:thon)?\b)|'
                          r'(?:\s*(\w+))\s*)(.*?)\s*%>(?s)')
escape_re = re.compile(r'\\\n|\\(\\|<%)')
NAMESTART = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
NAMECHARS = NAMESTART + '.0123456789'


def to_unicode_stmt(node, lineno=None):
    if isinstance(node, basestring):
        return ast.Const(node, lineno=lineno)
    if isinstance(node, ast.Const):
        return node
    return call_stmt('__to_unicode', [node], lineno)


def call_stmt(func, args, lineno):
    return ast.CallFunc(ast.Name(func, lineno=lineno),
                        args, lineno=lineno)


def parse_python(expr, type, filename, lineno):
    try:
        node = parse(expr, type)
    except SyntaxError, e:
        raise TemplateSyntaxError(str(e), filename, lineno + e.lineno - 1)
    nodes = [node]
    while nodes:
        n = nodes.pop()
        if hasattr(n, 'lineno'):
            n.lineno = (n.lineno or 1) + lineno - 1
        nodes.extend(n.getChildNodes())
    return node.node


def tokenize(source, filename):
    escape = escape_re.sub
    escape_repl = lambda m: m.group(1) or ''
    lineno = 1
    pos = 0

    for match in directive_re.finditer(source):
        start, end = match.span()
        if start > pos:
            data = source[pos:start]
            yield lineno, 'data', escape(escape_repl, data)
            lineno += data.count('\n')
        is_comment, is_code, cmd, args = match.groups()
        if is_code:
            yield lineno, 'code', args
        elif not is_comment:
            yield lineno, 'cmd', (cmd, args)
        lineno += source[start:end].count('\n')
        pos = end

    if pos < len(source):
        yield lineno, 'data', escape(escape_repl, source[pos:])


def transform(node, filename):
    root = ast.Module(None, node, lineno=1)
    nodes = [root]
    while nodes:
        node = nodes.pop()
        node.filename = filename
        if node.__class__ in (ast.Printnl, ast.Print):
            node.dest = ast.Name('__stream')
        nodes.extend(node.getChildNodes())
    return root


class TemplateSyntaxError(SyntaxError):

    def __init__(self, msg, filename, lineno):
        SyntaxError.__init__(self, msg)
        self.lineno = lineno
        self.filename = filename


class Parser(object):

    def __init__(self, gen, filename):
        self.gen = gen
        self.filename = filename
        self.lineno = 1

    def fail(self, msg):
        raise TemplateSyntaxError(msg, self.filename, self.lineno)

    def parse(self, needle=()):
        start_lineno = self.lineno
        result = []
        add = result.append
        for self.lineno, token, value in self.gen:
            if token == 'data':
                add(self.parse_data(value))
            elif token == 'code':
                add(self.parse_code(value.splitlines()))
            elif token == 'cmd':
                name, args = value
                if name in needle:
                    return name, args, ast.Stmt(result, lineno=start_lineno)
                if name in ('for', 'while'):
                    add(self.parse_loop(args, name))
                elif name == 'if':
                    add(self.parse_if(args))
                elif name in ('break', 'continue'):
                    if args:
                        self.fail('%s takes no arguments' % name)
                    add(ast.Stmt(name == 'break' and ast.Break or
                                 ast.Continue)(self.lineno), self.lineno)
                else:
                    self.fail('unknown directive %S' % name)
        if needle:
            self.fail('unexpected end of template')
        return ast.Stmt(result, lineno=start_lineno)

    def parse_loop(self, args, type):
        loop = parse_python('%s %s: pass' % (type, args), 'exec',
                            self.filename, self.lineno).nodes[0]
        tag, value, loop.body = self.parse(('end' + type,))
        if value:
            self.fail('unexpected data after end' + type)
        return loop

    def parse_if(self, args):
        cond = parse_python('if %s: pass' % args, 'exec',
                            self.filename, self.lineno).nodes[0]
        tag, value, body = self.parse(('else', 'elif', 'endif'))
        cond.tests[0] = (cond.tests[0][0], body)
        while 1:
            if tag == 'else':
                tag, value, cond.else_ = self.parse(('endif',))
            elif tag == 'elif':
                expr = parse_python(value, 'eval', self.filename, self.lineno)
                tag, value, body = self.parse(('else', 'elif', 'endif'))
                cond.tests.append((expr, body))
                continue
            break
        if value:
            self.fail('unexpected data after endif')
        return cond

    def parse_code(self, lines):
        margin = sys.maxint
        for line in lines[1:]:
            content = len(line.lstrip())
            if content:
                indent = len(line) - content
                margin = min(margin, indent)
        if lines:
            lines[0] = lines[0].lstrip()
        if margin < sys.maxint:
            for i in range(1, len(lines)):
                lines[i] = lines[i][margin:]
        while lines and not lines[-1]:
            lines.pop()
        while lines and not lines[0]:
            lines.pop(0)
        return parse_python('\n'.join(lines), 'exec', self.filename,
                            self.lineno)

    def parse_data(self, text):
        lineno = self.lineno
        offset = pos = 0
        end = len(text)
        escaped = False
        nodes = []
        start_lineno = lineno
        write = lambda *a: nodes.append(to_unicode_stmt(*a))

        while 1:
            if escaped:
                offset = text.find('$', offset + 2)
                escaped = False
            else:
                offset = text.find('$', pos)
            if offset < 0 or offset == end - 1:
                break
            next = text[offset + 1]

            if next == '{':
                if offset > pos:
                    data = text[pos:offset]
                    write(data, lineno)
                    lineno += data.count('\n')
                pos = offset + 2
                level = 1
                while level:
                    match = tokenprog.match(text, pos)
                    if match is None:
                        self.fail('invalid syntax')
                    pos = match.end()
                    token = match.group().strip()
                    if token in '{}':
                        level += token == '{' and 1 or -1
                data = text[offset + 2:pos - 1]
                write(parse_python(data, 'eval', self.filename, lineno),
                      lineno)
                lineno += data.count('\n')

            elif next in NAMESTART:
                if offset > pos:
                    data = text[pos:offset]
                    write(data, lineno)
                    lineno += data.count('\n')
                    pos = offset
                pos += 1
                while pos < end:
                    char = text[pos]
                    if char not in NAMECHARS:
                        break
                    pos += 1
                data = text[offset + 1:pos].strip()
                write(parse_python(text[offset + 1:pos].strip(), 'eval',
                                   self.filename, self.lineno))

            elif not escaped and next == '$':
                if offset > pos:
                    data = text[pos:offset]
                    write(data, lineno)
                    lineno += data.count('\n')
                escaped = True
                pos = offset + 1

            else:
                data = text[pos:offset + 1]
                write(data, lineno)
                lineno += data.count('\n')
                pos = offset + 1

        if pos < end:
            write(text[pos:], lineno)
        if len(nodes) == 1:
            return call_stmt('__write', [to_unicode_stmt(nodes[0],
                             lineno)], lineno)
        else:
            node = call_stmt('__write_many', nodes, lineno)
        return ast.Discard(node, lineno=lineno)


class UndefinedType(object):
    __slots__ = ()

    def __new__(self):
        raise TypeError('cannot create %r instances' %
                        self.__class__.__name__)

    def __iter__(self):
        return iter(())

    def __repr__(self):
        return 'Undefined'

    def __str__(self):
        return ''


class Context(object):

    def __init__(self, namespace, encoding, errors):
        self.encoding = encoding
        self.errors = errors
        self.join = u''.join
        self._namespace = namespace
        self._buffer = []
        self._namespace.update(
            __join=self.join,
            __to_unicode=self.to_unicode,
            __stream=self,
            __write=self.write,
            __write_many=lambda *a: self._buffer.extend(
                                    map(self.to_unicode, a))
        )

    def write(self, value):
        self._buffer.append(self.to_unicode(value))

    def to_unicode(self, value):
        if isinstance(value, str):
            return value.decode(self.encoding, self.errors)
        return unicode(value)

    def get_value(self, as_unicode=True):
        rv = self.join(self._buffer)
        if not as_unicode:
            return rv.encode(self.encoding, self.errors)
        return rv

    def __getitem__(self, key):
        return self._namespace.get(key, Undefined)

    def __setitem__(self, key, value):
        self._namespace[key] = value

    def __delitem__(self, key):
        del self._namespace[key]


Undefined = object.__new__(UndefinedType)


class Template(object):
    """
    Represents a simple text based template.
    """
    default_context = {
        'escape':           utils.escape,
        'url_quote':        utils.url_quote,
        'url_quote_plus':   utils.url_quote_plus,
        'url_encode':       utils.url_encode
    }

    def __init__(self, source, filename='<template>', encoding='utf-8',
                 errors='strict', unicode_mode=True):
        node = Parser(tokenize('\n'.join(source.splitlines()),
                               filename), filename).parse()
        self.code = ModuleCodeGenerator(transform(node, filename)).getCode()
        self.filename = filename
        self.encoding = encoding
        self.errors = errors
        self.unicode_mode = unicode_mode

    def from_file(cls, file, encoding='utf-8', errors='strict',
                  unicode_mode=True):
        if isinstance(file, basestring):
            f = open(file, 'r')
            close = True
        else:
            close = False
        try:
            data = f.read().decode(encoding, errors)
        finally:
            if close:
                f.close()
        return cls(data, getattr(f, 'name', '<template>'), encoding,
                   errors, unicode_mode)
    from_file = classmethod(from_file)

    def render(self, *args, **kwargs):
        ns = self.default_context.copy()
        ns.update(*args, **kwargs)
        context = Context(ns, self.encoding, self.errors)
        exec self.code in None, context
        return context.get_value(self.unicode_mode)
