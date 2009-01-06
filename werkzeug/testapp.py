# -*- coding: utf-8 -*-
"""
    werkzeug.testapp
    ~~~~~~~~~~~~~~~~

    Provide a small test application that can be used to test a WSGI server
    and check it for WSGI compliance.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.templates import Template
from werkzeug.wrappers import BaseRequest as Request, BaseResponse as Response


logo = Response('''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
='''.decode('base64'), mimetype='image/png')


TEMPLATE = Template(ur'''\
<%py
    import sys, os
    from textwrap import wrap
    try:
        import pkg_resources
    except ImportError:
        eggs = None
    else:
        eggs = list(pkg_resources.working_set)
        eggs.sort(lambda a, b: cmp(a.project_name.lower(),
                                   b.project_name.lower()))
    sorted_environ = req.environ.items()
    sorted_environ.sort(lambda a, b: cmp(str(a[0]).lower(), str(b[0]).lower()))
%>
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
  "http://www.w3.org/TR/html4/loose.dtd">
<title>WSGI Information</title>
<style type="text/css">
  body      { font-family: 'Lucida Grande', 'Lucida Sans Unicode', 'Geneva',
              'Verdana', sans-serif; background-color: #AFC1C4; color: #000;
              text-align: center; margin: 1em; padding: 0; }
  #logo     { float: right; padding: 10px; }
  div.box   { text-align: left; width: 45em; padding: 1em; margin: auto;
              border: 1px solid #aaa; background-color: white; }
  h1        { color: #11557C; font-size: 2em; margin: 0 0 0.8em 0; }
  h2        { font-size: 1.4em; margin: 1em 0 0.5em 0; }
  table     { width: 100%; border-collapse: collapse; border: 1px solid #AFC5C9 }
  table th  { background-color: #AFC1C4; color: white; font-size: 0.72em;
              font-weight: normal; width: 18em; vertical-align: top;
              padding: 0.5em 0 0.1em 0.5em; }
  table td  { border: 1px solid #AFC5C9; padding: 0.1em 0 0.1em 0.5em; }
  code      { font-family: 'Consolas', 'Monaco', 'Bitstream Vera Sans Mono',
              monospace; font-size: 0.7em; }
  ul li     { line-height: 1.5em; }
</style>
<div class="box">
  <img src="?resource=logo" id="logo" alt="[The Werkzeug Logo]" />
  <h1>WSGI Information</h1>
  <p>
    This page displays all available information about the WSGI server and
    the underlying Python interpreter that are available.
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
</div>''')


def test_app(environ, start_response):
    """Simple test application that dumps the environment."""
    req = Request(environ, populate_request=False)
    if req.args.get('resource') == 'logo':
        response = logo
    else:
        response = Response(TEMPLATE.render(req=req), mimetype='text/html')
    return response(environ, start_response)


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('localhost', 5000, test_app, use_reloader=True)
