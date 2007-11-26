# -*- coding: utf-8 -*-
"""
    werkzeug.testapp
    ~~~~~~~~~~~~~~~~

    Provide a small test application that can be used to test a WSGI server
    and check it for WSGI compliance.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
try:
    import pkg_resources
except ImportError:
    pkg_resources = None
from werkzeug.templates import Template
from werkzeug.wrappers import BaseRequest as Request


LOGO = '''\
R0lGODlhoACgAOMIAAEDACwpAEpCAGdgAJaKAM28AOnVAP3rAP//////////////////////////
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'''

TEMPLATE = Template(ur'''\
<%py
    import sys
    import os
    from textwrap import wrap

    sorted_environ = req.environ.items()
    sorted_environ.sort(lambda a, b: cmp(str(a[0]).lower(), str(b[0]).lower()))
%>
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
  "http://www.w3.org/TR/html4/loose.dtd">
<html>
  <head>
    <title>WSGI Information</title>
    <style type="text/css">
      body {
        font-family: sans-serif;
        background-color: #333;
        text-align: center;
        margin: 1em;
        padding: 0;
      }

      #logo {
        float: right;
        padding: 10px;
      }

      div.box {
        text-align: left;
        width: 45em;
        padding: 1em;
        margin: 0 auto 0 auto;
        border: 1px solid black;
        background-color: white;
      }

      h1 {
        color: #444;
        font-size: 2em;
        margin: 0 0 1em 0;
        font-family: 'Georgia', serif;
      }

      h2 {
        color: #333;
        font-size: 1.4em;
        margin: 1em 0 0.5em 0;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        border: 1px solid #ccc;
      }

      table th {
        background-color: #555;
        color: white;
        font-size: 0.7em;
        font-weight: normal;
        width: 18em;
        padding: 0.5em 0 0.1em 0.5em;
        vertical-align: top;
      }

      table td {
        border: 1px solid #ccc;
        padding: 0.1em 0 0.1em 0.5em;
      }

      table td code {
        font-family: 'Consolas', 'Monaco', 'Bitstream Vera Sans', monospace;
        font-size: 0.7em;
      }

      ul li {
        line-height: 1.5em;
      }
    </style>
  </head>
  <body>
    <div class="box">
      <img src="?resource=logo" id="logo" alt="" />
      <h1>WSGI Information</h1>
      <p>
        This page displays all available information about the WSGI server and
        the underlaying Python interpreter that are available.
      </p>
      <h2 id="python-interpreter">Python Interpreter</h2>
      <table>
        <tr>
          <th>Python Version</th>
          <td>${'<br>'.join(escape(sys.version).splitlines())}</td>
        </tr>
        <tr>
          <th>Platform</th>
          <td>$escape(sys.platform) [$escape(os.name)]</td>
        </tr>
        <tr>
          <th>API Version</th>
          <td>$sys.api_version</td>
        </tr>
        <tr>
          <th>Byteorder</th>
          <td>$sys.byteorder</td>
        </tr>
      </table>
      <h2 id="wsgi-environment">WSGI Environment</h2>
      <table>
      <% for key, value in sorted_environ %>
        <tr>
          <th>$escape(str(key))</th>
          <td><code>${' '.join(wrap(escape(repr(value))))}</code></td>
        </tr>
      <% endfor %>
      </table>
      <% if eggs %>
      <h2 id="installed-eggs">Installed Eggs</h2>
      <ul>
      <% for egg in eggs %>
        <li>$escape(egg.project_name) <small>[$escape(egg.version)]</small></li>
      <% endfor %>
      </ul>
      <% endif %>
    </div>
  </body>
</html>
''', unicode_mode=False)


def test_app(environ, start_response):
    req = Request(environ, populate_request=False)
    if req.args.get('resource') == 'logo':
        image = LOGO.decode('base64')
        start_response('200 OK', [('Content-Type', 'image/gif'),
                                  ('Content-Length', str(len(image)))])
        return [image]
    start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
    eggs = None
    if pkg_resources is not None:
        eggs = list(pkg_resources.working_set)
        eggs.sort(lambda a, b: cmp(a.project_name.lower(),
                                   b.project_name.lower()))
    return [TEMPLATE.render(req=req, eggs=eggs)]


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('localhost', 5000, test_app, use_reloader=True)
