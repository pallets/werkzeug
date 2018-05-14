# -*- coding: utf-8 -*-
from __future__ import print_function

import inspect
import re

from pallets_sphinx_themes import ProjectLink, get_version

# Project --------------------------------------------------------------

project = 'Werkzeug'
copyright = '2011 Pallets Team'
author = 'Pallets Team'
release, version = get_version('Werkzeug')

# General --------------------------------------------------------------

master_doc = 'index'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'werkzeug': ('http://werkzeug.pocoo.org/docs/', None),
    'jinja': ('http://jinja.pocoo.org/docs/', None),
}

# HTML -----------------------------------------------------------------

html_theme = 'werkzeug'
html_context = {
    'project_links': [
        ProjectLink('Donate to Pallets', 'https://psfmember.org/civicrm/contribute/transact?reset=1&id=20'),
        ProjectLink('Werkzeug Website', 'https://palletsprojects.com/p/werkzeug/'),
        ProjectLink('PyPI releases', 'https://pypi.org/project/Werkzeug/'),
        ProjectLink('Source Code', 'https://github.com/pallets/werkzeug/'),
        ProjectLink('Issue Tracker', 'https://github.com/pallets/werkzeug/issues/'),
    ],
    'canonical_url': 'http://werkzeug.pocoo.org/docs/{}/'.format(version),
    'carbon_ads_args': 'zoneid=1673&serve=C6AILKT&placement=pocooorg',
}
html_sidebars = {
    'index': [
        'project.html',
        'versions.html',
        'carbon_ads.html',
        'searchbox.html',
    ],
    '**': [
        'localtoc.html',
        'relations.html',
        'versions.html',
        'carbon_ads.html',
        'searchbox.html',
    ]
}
html_static_path = ['_static']
html_favicon = '_static/favicon.ico'
html_logo = '_static/werkzeug.png'
html_additional_pages = {
    '404': '404.html',
}
html_show_sourcelink = False

# LaTeX ----------------------------------------------------------------

latex_documents = [
    (master_doc, 'Werkzeug.tex', 'Werkzeug Documentation', 'Pallets Team', 'manual'),
]
latex_use_modindex = False
latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '12pt',
    'fontpkg': r'\usepackage{mathpazo}',
    'preamble': r'\usepackage{werkzeugstyle}',
}
latex_use_parts = True
latex_additional_files = ['werkzeugstyle.sty', 'logo.pdf']

# linkcheck ------------------------------------------------------------

linkcheck_anchors = False

# Local Extensions -----------------------------------------------------

def unwrap_decorators():
    import sphinx.util.inspect as inspect
    import functools

    old_getargspec = inspect.getargspec
    def getargspec(x):
        return old_getargspec(getattr(x, '_original_function', x))
    inspect.getargspec = getargspec

    old_update_wrapper = functools.update_wrapper
    def update_wrapper(wrapper, wrapped, *a, **kw):
        rv = old_update_wrapper(wrapper, wrapped, *a, **kw)
        rv._original_function = wrapped
        return rv
    functools.update_wrapper = update_wrapper


unwrap_decorators()
del unwrap_decorators


_internal_mark_re = re.compile(r'^\s*:internal:\s*$(?m)', re.M)


def skip_internal(app, what, name, obj, skip, options):
    docstring = inspect.getdoc(obj) or ''

    if skip or _internal_mark_re.search(docstring) is not None:
        return True


def cut_module_meta(app, what, name, obj, options, lines):
    """Remove metadata from autodoc output."""
    if what != 'module':
        return

    lines[:] = [
        line for line in lines
        if not line.startswith((':copyright:', ':license:'))
    ]


def setup(app):
    app.connect('autodoc-skip-member', skip_internal)
    app.connect('autodoc-process-docstring', cut_module_meta)
