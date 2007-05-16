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

    :copyright: 2006 by Armin Ronacher, Georg Brandl.
    :license: BSD License.
"""
import re
from cgi import escape

tag_re = re.compile(r'(.*?)(<\%(?!\%).*?(?<!\%)\%>)(?sm)')


class TemplateFilter(object):
    """
    Creates a template filter for a function.
    """

    def __init__(self, func, args=None, kwargs=None):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __ror__(self, value):
        return self.func(value, *(self.args or ()), **(self.kwargs or {}))

    def __call__(self, *args, **kwargs):
        if self.args is self.kwargs is None:
            raise TypeError('filter is not callable')
        return TemplateFilter(self.func, args, kwargs)


class Template(object):
    """
    A mini template. Usage::

        t = Template('templatetext')
        t.render(**templatecontext)
    """

    def __init__(self, source):
        lines = ['def __generate():', '    if 0: yield None']
        indention = 1
        write = lambda d, o: lines.append(('    ' * (indention - o)) + d)

        source = u'\n'.join(source.replace('\\\n', ' ').splitlines())
        match = None
        for match in tag_re.finditer(source):
            write('yield %r' % match.group(1), 0)
            tag = match.group(2)
            if tag.startswith('<%='):
                write('yield unicode(%s)' % tag[3:-2].strip(), 0)
            elif tag.startswith('<%!'):
                tmp = tag[3:-2].splitlines() or ['']
                if tmp.pop(0).strip():
                    raise SyntaxError('invalid syntax for long block')
                margin = None
                for line in tmp:
                    contents = len(line.lstrip())
                    if contents:
                        indent = len(line) - contents
                        if margin is None or indent < margin:
                            margin = indent
                for idx, item in enumerate(tmp):
                    write(item[margin or 0:], 0)
            elif not tag.startswith('<%#'):
                data = tag[2:-2].strip()
                if data == 'end':
                    indention -= 1
                elif data.split(None, 1)[0].rstrip('\t :') in \
                     ('else', 'elif', 'except'):
                    write(data, 1)
                else:
                    write(data, 0)
                    if data.rstrip().endswith(':'):
                        indention += 1
        rest = source[(match and match.end() or 0):]
        if rest:
            write('yield %r' % rest, 0)
        source = '\n'.join(lines).replace('<%%', '<%').replace('%%>', '%>')

        self.code = compile(source, '<template>', 'exec')
        self.filters = DEFAULT_FILTERS.copy()

    def add_filter(self, name, func):
        self.filters[name] = TemplateFilter(func)

    def render(self, *args, **kwargs):
        ns = self.filters.copy()
        ns.update(*args, **kwargs)
        tmp = {}
        exec self.code in ns, tmp
        return u''.join(tuple(tmp['__generate']()))


DEFAULT_FILTERS = {
    'escape': TemplateFilter(lambda s, *a, **k: escape(unicode(s), *a, **k))
}
