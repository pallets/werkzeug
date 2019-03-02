# -*- coding: utf-8 -*-
"""
    coolmagic.views.static
    ~~~~~~~~~~~~~~~~~~~~~~

    Some static views.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
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
