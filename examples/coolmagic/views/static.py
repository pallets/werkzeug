# -*- coding: utf-8 -*-
"""
    coolmagic.views.static
    ~~~~~~~~~~~~~~~~~~~~~~

    Some static views.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
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


@export(None, template='static/not_found.html')
def not_found():
    """
    This function is always executed if an url does not
    match or a `NotFound` exception is raised.
    """
    pass
