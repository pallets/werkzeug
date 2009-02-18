# -*- coding: utf-8 -*-
"""
    Werkzeug Sphinx Extensions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Provides some more helpers for the werkzeug docs.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from sphinx.ext.autodoc import cut_lines


def setup(app):
    app.connect('autodoc-process-docstring', cut_lines(3, 3, what=['module']))
