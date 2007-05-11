# -*- coding: <%= FILE_ENCODING %> -*-
from <%= PACKAGE %>.utils import Response


def index(req):
    return Response(u'''
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
      "http://www.w3.org/TR/html4/strict.dtd">
    <title>Welcome to Werkzeug</title>
    <style type="text/css">
      body { font-family: 'Trebuchet MS', sans-serif; font-size: 16px;
             margin: 0; padding: 20px; }
      h1 { color: #a00; margin: 0 0 20px 0; padding: 0; }
      tt { background-color: #eee; font-family: monospace; font-size: 13px; }
    </style>
    <h1>Welcome to Werkzeug</h1>
    <p>
      Welcome to Werkzeug. This file structure was created by
      Werkzeug automatically in order to help you creating your
      first WSGI based application.
    </p>
    <p>
      Here a small explanation for this structure:
    </p>
    <ul>
      <li><tt>start-<%= PACKAGE %>.py</tt> &mdash; minimal python
          script that spawns a wsgiref server for this application</li>
      <li><tt><%= PACKAGE %>/application.py</tt> &mdash; implements
          the WSGI application and dispatches requests.</li>
      <li><tt><%= PACKAGE %>/urls.py</tt> &mdash; contains the url
          mapping definitions that map to the view functions.</li>
      <li><tt><%= PACKAGE %>/utils.py</tt> &mdash; contains subclasses
          of the base request and response objects.</li>
      <li><tt><%= PACKAGE %>/views/</tt> &mdash; contains all the
          modules with the view functions.</li>
    </ul>
    <p>
      To change this page to go <tt><%= PACKAGE %>/urls.py</tt> and
      change the rules there in order to point to your view functions.
      You can then remove the <tt>default.py</tt> views.
    </p>
    ''', mimetype='text/html')


def not_found(req):
    return Response(u'''
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
      "http://www.w3.org/TR/html4/strict.dtd">
    <h1>Page Not Found</h1>''',
    mimetype='text/html', status=404)
