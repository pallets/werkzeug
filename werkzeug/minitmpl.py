# -*- coding: utf-8 -*-
"""
    werkzeug.minitmpl
    ~~~~~~~~~~~~~~~~~

    A very simple Python "Template Engine". In fact it just recognizes
    PHP like blocks and executes the code in them::

        t = Template('<% for u in users: %><%= u['username'] %>\n<% end %>')
        t.render(users=[{'username': 'John'},
                        {'username': 'Jane'}])

    would result in::

        John
        Jane

    Syntax Elements::

        <% code %>
            executes code

        <%= variable %>
            prints out the variable value

        <%# comment %>
            is just a comment

        <%% / %%>
            escaped tags


    :copyright: 2006 by Armin Ronacher, Georg Brandl.
    :license: BSD License.
"""
import re
from cgi import escape

tag_re = re.compile(r'(.*?)(<\%[=\#|]?(?!%)\s*.*?\s*\%(?!\%)>)(?uism)')


def _unescape(s):
    return s.replace('<%%', '<%').replace('%%>', '%>')


def _tokenize(source):
    source = u'\n'.join(source.splitlines())
    match = None
    for match in tag_re.finditer(source):
        data = match.group(1)
        yield 'TEXT', _unescape(data)
        tag = _unescape(match.group(2))
        if tag.startswith('<%='):
            yield 'VARIABLE', tag[3:-2].strip()
        elif not tag.startswith('<%#'):
            token_type = 'BLOCK'
            lines = tag[2:-2].strip().splitlines()
            if len(lines) > 1:
                new_lines = []
                indent = match.start(2) - match.end(1) + 4
                for line in lines[1:]:
                    if line[:indent].strip():
                        raise SyntaxError()
                    new_lines.append(line[indent:])
                data = '\n'.join(lines[:1] + new_lines)
            else:
                data = lines[0]
            yield token_type, data
    rest = source[(match and match.end() or 0):]
    if rest:
        yield 'TEXT', _unescape(rest)


class TemplateFilter(object):
    """
    Creates a template filter for a function.
    """

    def __init__(self, func):
        self.func = func

    def __ror__(self, value):
        return self.func(value)

    def __call__(self, *args, **kwargs):
        return PreparedTemplateFilter(self.func, args, kwargs)


class PreparedTemplateFilter(object):
    """
    Helper for `TemplateFilter`
    """

    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __ror__(self, value):
        return self.func(value, *self.args, **self.kwargs)


class Template(object):
    """
    A mini template. Usage::

        t = Template('templatetext')
        t.render(**templatecontext)
    """
    filters = {
        'escape':       TemplateFilter(lambda s, *a, **kw:
                                       escape(unicode(s), *a, **kw))
    }

    def __init__(self, source):
        sourcelines = ['def generate():', '    if 0: yield None']
        indention = 1

        write = lambda d, o: sourcelines.append(('    ' * (indention - o)) + d)
        def write_block(d):
            for line in d.splitlines():
                write(line, 0)

        for token_type, data in _tokenize(source):
            if token_type == 'TEXT':
                write('yield %r' % data, 0)
            elif token_type == 'VARIABLE':
                write('yield unicode(%s)' % data, 0)
            elif token_type == 'BLOCK':
                statement = data.split()[0]
                if data == 'end':
                    indention -= 1
                elif statement in ('else:', 'elif', 'except:'):
                    write(data, 1)
                else:
                    write_block(data)
                    if data.rstrip().endswith(':'):
                        indention += 1
        source = '\n'.join(sourcelines)
        self.code = compile(source, '<template>', 'exec')
        self._generate = None
        self.filters = self.filters.copy()

    def add_filter(self, name, func):
        self.filters[name] = TemplateFilter(func)

    def render(self, *args, **kwargs):
        ns = self.filters.copy()
        ns.update(*args, **kwargs)
        tmp = {}
        exec self.code in ns, tmp
        return u''.join(tuple(tmp['generate']()))
