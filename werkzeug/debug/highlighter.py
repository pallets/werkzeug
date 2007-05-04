# -*- coding: utf-8 -*-
"""
    werkzeug.debug.highlighter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Simple Python source code highlighter.

    :copyright: 2007 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import re
import token
import keyword
import tokenize
from cgi import escape
from StringIO import StringIO


class PythonParser(object):
    """
    Simple python sourcecode highlighter.

    Usage::

        p = PythonParser(source)
        p.parse()
        for line in p.get_html_output():
            print line
    """

    _KEYWORD = token.NT_OFFSET + 1
    _TEXT    = token.NT_OFFSET + 2
    _classes = {
        token.NUMBER:       'num',
        token.OP:           'op',
        token.STRING:       'str',
        tokenize.COMMENT:   'cmt',
        token.NAME:         'id',
        token.ERRORTOKEN:   'error',
        _KEYWORD:           'kw',
        _TEXT:              'txt',
    }

    def __init__(self, raw):
        self.raw = raw.expandtabs(8)
        if isinstance(self.raw, unicode):
            self.raw = self.raw.encode('utf-8', 'ignore')
        self.out = StringIO()

    def parse(self):
        self.lines = [0, 0]
        pos = 0
        while 1:
            pos = self.raw.find('\n', pos) + 1
            if not pos:
                break
            self.lines.append(pos)
        self.lines.append(len(self.raw))

        self.pos = 0
        text = StringIO(self.raw)
        try:
            tokenize.tokenize(text.readline, self)
        except tokenize.TokenError:
            pass

    def get_html_output(self):
        """ Return line generator. """
        def html_splitlines(lines):
            # this cool function was taken from trac.
            # http://projects.edgewall.com/trac/
            open_tag_re = re.compile(r'<(\w+)(\s.*)?[^/]?>')
            close_tag_re = re.compile(r'</(\w+)>')
            open_tags = []
            for line in lines:
                for tag in open_tags:
                    line = tag.group(0) + line
                open_tags = []
                for tag in open_tag_re.finditer(line):
                    open_tags.append(tag)
                open_tags.reverse()
                for ctag in close_tag_re.finditer(line):
                    for otag in open_tags:
                        if otag.group(1) == ctag.group(1):
                            open_tags.remove(otag)
                            break
                for tag in open_tags:
                    line += '</%s>' % tag.group(1)
                yield line

        return list(html_splitlines(self.out.getvalue().splitlines()))

    def __call__(self, toktype, toktext, (srow,scol), (erow,ecol), line):
        oldpos = self.pos
        newpos = self.lines[srow] + scol
        self.pos = newpos + len(toktext)

        if toktype in [token.NEWLINE, tokenize.NL]:
            self.out.write('\n')
            return

        if newpos > oldpos:
            self.out.write(self.raw[oldpos:newpos])

        if toktype in [token.INDENT, token.DEDENT]:
            self.pos = newpos
            return

        if token.LPAR <= toktype and toktype <= token.OP:
            toktype = token.OP
        elif toktype == token.NAME and keyword.iskeyword(toktext):
            toktype = self._KEYWORD
        clsname = self._classes.get(toktype, 'txt')

        self.out.write('<span class="code-item p-%s">' % clsname)
        self.out.write(escape(toktext))
        self.out.write('</span>')
