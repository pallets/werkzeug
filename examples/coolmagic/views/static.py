# -*- coding: utf-8 -*-
"""
    coolmagic.views.static
    ~~~~~~~~~~~~~~~~~~~~~~

    Some static views.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from coolmagic.helpers import *


@export('/', template='static/index.html')
def index():
    pass


@export('/about', template='static/about.html')
def about():
    pass


@export('/broken')
def broken():
    foo = request.args.get('foo', 42)
    raise RuntimeError('that\'s really broken')


@export(404, template='static/not_found.html')
def not_found():
    """
    This function is always executed if an url does not
    match or `abort(404)` is called.
    """
    pass


@export(302)
def redirect_to(url):
    """
    Helper function for ``redirect(url[, 302])``.
    """
    resp = Response('Redirecting to %s...' % url,
                    mimetype='text/html', status=302)
    resp.headers['Location'] = url
    return resp
