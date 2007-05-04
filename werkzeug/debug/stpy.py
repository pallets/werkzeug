# -*- coding: utf-8 -*-
"""
    werkzeug.debug.stpy
    ~~~~~~~~~~~~~~~~~~~

    A very simple Python "Template Engine". In fact it just look up
    PHP like blocks and executes the code::

        t = Template('<? for u in users ?><?= u['username'] ?>\n<? end ?>')
        t.render(users=[{'username': 'John'},
                        {'username': 'Jane'}])

    would result in::

        John
        Jane

    Syntax Elements::

        <? code ?>
            executes code

        <?= variable ?>
            prints out the variable value

        <?& variable ?>
            prints out the variable value, HTML-escaped

        <?# comment ?>
            is just a comment


    :copyright: 2006 by Armin Ronacher, Georg Brandl.
    :license: BSD License.
"""
import re
from cgi import escape

tag_re = re.compile(r'(.*?)(<\?[=\#|]?\s*.*?\s*\?>)(?uism)')


class Template(object):

    def __init__(self, source):
        sourcelines = []
        indention = 0
        def write(data, offset):
            sourcelines.append(('    ' * (indention - offset)) + data)

        for token_type, data in self.tokenize(source):
            if token_type == 'TEXT':
                if data:
                    write('__write(%r)' % data, 0)
            elif token_type == 'VARIABLE':
                if data:
                    write('__write_var(%s)' % data, 0)
            elif token_type == 'EVARIABLE':
                if data:
                    write('__write_var(__escape(%s))' % data, 0)
            elif token_type == 'BLOCK':
                statement = data.split()[0]
                if data == 'end':
                    indention -= 1
                elif statement in ('else:', 'elif', 'except:'):
                    write(data, 1)
                else:
                    write(data, 0)
                    indention += 1
        source = '\n'.join(sourcelines)
        self.code = compile(source, '<template>', 'exec')

    def tokenize(self, source):
        remove_newline = False
        for match in tag_re.finditer(source):
            data = match.group(1)
            if remove_newline and data.startswith('\n'):
                data = data[1:]
            yield 'TEXT', data
            remove_newline = False
            tag = match.group(2)
            if tag.startswith('<?='):
                yield 'VARIABLE', tag[3:-2].strip()
            elif tag.startswith('<?&'):
                yield 'EVARIABLE', tag[3:-2].strip()
            elif tag.startswith('<?#'):
                remove_newline = True
            else:
                token_type = 'BLOCK'
                lines = tag[2:-2].strip().splitlines()
                if len(lines) > 1:
                    new_lines = []
                    indent = match.start(2) - match.end(1) + 3
                    for line in lines[1:]:
                        if line[:indent].strip():
                            raise SyntaxError()
                        new_lines.append(line[indent:])
                    data = '\n'.join(lines[:1] + new_lines)
                else:
                    data = lines[0]
                remove_newline = True
                yield token_type, data
        rest = source[match.end():]
        if remove_newline and rest.startswith('\n'):
            rest = rest[1:]
        if rest:
            yield 'TEXT', rest

    def get_variable(self, value):
        if isinstance(value, unicode):
            return value.encode('utf-8')
        elif not isinstance(value, str):
            return str(value)
        return value

    def render(self, *args, **kwargs):
        lines = []
        d = dict(*args, **kwargs)
        d['__write'] = lines.append
        d['__write_var'] = lambda x: lines.append(self.get_variable(x))
        d['__escape'] = escape
        exec self.code in d
        return ''.join(lines)
