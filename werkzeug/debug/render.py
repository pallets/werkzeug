# -*- coding: utf-8 -*-
"""
    werkzeug.debug.render
    ~~~~~~~~~~~~~~~~~~~~~

    Render the traceback debugging page.

    :copyright: 2007 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pprint
from cgi import escape

from werkzeug.debug.templates import JAVASCRIPT, STYLESHEET


class DebugRenderer(object):

    def __init__(self, context, evalex):
        self.c = context
        self.evalex = evalex

    def render(self):
        return '\n'.join([
            self.header(),
            self.traceback(),
            self.request_information(),
            self.footer()
        ])

    def header(self):
        data = [
            '<script type="text/javascript">%s</script>' % JAVASCRIPT,
            '<style type="text/css">%s</style>' % STYLESHEET,
            '<div id="wsgi-traceback">'
        ]

        if hasattr(self.c, 'exception_type'):
            title = escape(self.c.exception_type)
            exc = escape(self.c.exception_value)
            data += [
                '<h1>%s</h1>' % title,
                '<p class="errormsg">%s</p>' % exc
            ]

        if hasattr(self.c, 'last_frame'):
            data += [
                '<p class="errorline">%s in %s, line %s</p>' % (
                escape(self.c.last_frame['filename']),
                escape(self.c.last_frame['function']),
                self.c.last_frame['lineno'])
            ]

        return '\n'.join(data)

    def render_code(self, frame):
        def render_line(mode, lineno, code):
            return ''.join([
                '<tr class="%s">' % mode,
                '<td class="lineno">%i</td>' % lineno,
                '<td class="code">%s&nbsp;</td></tr>' % code
            ])

        tmp = ['<table class="code">']
        lineno = frame['context_lineno']
        if not lineno is None:
            lineno += 1
            for l in frame['pre_context']:
                tmp.append(render_line('pre', lineno, l))
                lineno += 1
            tmp.append(render_line('cur', lineno, frame['context_line']))
            lineno += 1
            for l in frame['post_context']:
                tmp.append(render_line('post', lineno, l))
                lineno += 1
        else:
            tmp.append(render_line('cur', 1, 'Sourcecode not available'))
        tmp.append('</table>')

        return '\n'.join(tmp)

    def var_table(self, var):
        # simple data types
        if isinstance(var, basestring) or isinstance(var, float)\
           or isinstance(var, int) or isinstance(var, long):
            return ('<table class="vars"><tr><td class="value">%r'
                    '</td></tr></table>' % escape(repr(var)))

        # dicts
        if isinstance(var, dict) or hasattr(var, 'items'):
            items = var.items()
            items.sort()

            # empty dict
            if not items:
                return ('<table class="vars"><tr><th>no data given'
                        '</th></tr></table>')

            result = ['<table class="vars"><tr><th>Name'
                      '</th><th>Value</th></tr>']
            for key, value in items:
                try:
                    val = escape(pprint.pformat(value))
                except:
                    val = '?'
                result.append('<tr><td class="name">%s</td><td class="value">%s'
                              '</td></tr>' % (escape(repr(key)), val))
            result.append('</table>')
            return '\n'.join(result)

        # lists
        if isinstance(var, list):
            # empty list
            if not var:
                return ('<table class="vars"><tr><th>no data given'
                        '</th></tr></table>')

            result = ['<table class="vars">']
            for line in var:
                try:
                    val = escape(pprint.pformat(line))
                except:
                    val = '?'
                result.append('<tr><td class="value">%s</td></tr>' % (val))
            result.append('</table>')
            return '\n'.join(result)

        # unknown things
        try:
            value = escape(repr(var))
        except:
            value = '?'
        return '<table class="vars"><tr><th>%s</th></tr></table>' % value

    def exec_code_table(self, uid):
        return '''
        <table class="exec_code">
          <tr>
            <td class="output" colspan="2"><pre id="output-%(tb_uid)s-%(frame_uid)s"></pre></td>
           </tr>
          <tr>
            <td class="input">
              <textarea class="small" id="input-%(tb_uid)s-%(frame_uid)s" value=""></textarea>
            </td>
            <td class="extend">
              <input type="button" onclick="toggleExtend('%(tb_uid)s', '%(frame_uid)s')" value="extend">
            </td>
          </tr>
        </table>
        ''' % {
            'target': '#',
            'tb_uid': self.c.tb_uid,
            'frame_uid': uid
        }

    def traceback(self):
        if not hasattr(self.c, 'frames'):
            return ''

        result = ['<h2 onclick="change_tb()" class="tb">Traceback (click to switch to raw view)</h2>']
        result.append('<div id="interactive"><p class="text">A problem occurred in your Python WSGI'
        ' application. Here is the sequence of function calls leading up to'
        ' the error, in the order they occurred. Click on a header to show'
        ' context lines.</p>')

        for num, frame in enumerate(self.c.frames):
            line = [
                '<div class="frame" id="frame-%i">' % num,
                '<h3 class="fn">%s in %s</h3>' % (
                    escape(frame['function']),
                    escape(frame['filename'])
                ),
                self.render_code(frame),
            ]

            if frame['vars']:
                line.append('\n'.join([
                    '<h3 class="indent">▸ local variables</h3>',
                    self.var_table(frame['vars'])
                ]))

            if self.evalex and self.c.tb_uid:
                line.append('\n'.join([
                    '<h3 class="indent">▸ execute code</h3>',
                    self.exec_code_table(frame['frame_uid'])
                ]))

            line.append('</div>')
            result.append(''.join(line))
        result.append('\n'.join([
            '</div>',
            self.plain()
        ]))
        return '\n'.join(result)

    def plain(self):
        if not hasattr(self.c, 'plaintb'):
            return ''
        return '''
        <div id="plain">
        <p class="text">Here is the plain Python traceback for copy and paste:</p>
        <pre class="plain">\n%s</pre>
        </div>
        ''' % self.c.plaintb

    def request_information(self):
        result = [
            '<h2>Request Data</h2>',
            '<p class="text">The following list contains all important',
            'request variables. Click on a header to expand the list.</p>'
        ]

        if not hasattr(self.c, 'frames'):
            del result[0]

        for key, info in self.c.req_vars:
            result.append('<dl><dt>%s</dt><dd>%s</dd></dl>' % (
                escape(key), self.var_table(info)
            ))

        return '\n'.join(result)

    def footer(self):
        return '\n'.join([
            '<script type="text/javascript">initTB();</script>',
            '</div>',
            '<div class="footer">Brought to you by '
            '<span class="arthur">DON\'T PANIC</span>, your friendly '
            'Colubrid traceback interpreter system.</div>',
            hasattr(self.c, 'plaintb')
                and ('<!-- Plain traceback:\n\n%s-->' % self.c.plaintb)
                or '',
        ])
