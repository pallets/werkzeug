# -*- coding: utf-8 -*-
from pallets_sphinx_themes import ProjectLink, get_version

# Project --------------------------------------------------------------

project = 'Werkzeug'
copyright = '2007 Pallets Team'
author = 'Pallets Team'
release, version = get_version('Werkzeug')

# General --------------------------------------------------------------

master_doc = 'index'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
    'pallets_sphinx_themes',
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
        ProjectLink('Donate to Pallets', 'https://www.palletsprojects.com/donate'),
        ProjectLink('Werkzeug Website', 'https://palletsprojects.com/p/werkzeug/'),
        ProjectLink('PyPI releases', 'https://pypi.org/project/Werkzeug/'),
        ProjectLink('Source Code', 'https://github.com/pallets/werkzeug/'),
        ProjectLink('Issue Tracker', 'https://github.com/pallets/werkzeug/issues/'),
    ],
}
html_sidebars = {
    'index': [
        'project.html',
        'versions.html',
        'searchbox.html',
    ],
    '**': [
        'localtoc.html',
        'relations.html',
        'versions.html',
        'searchbox.html',
    ]
}
singlehtml_sidebars = {
    "index": [
        "project.html",
        "versions.html",
        "localtoc.html",
    ]
}
html_static_path = ['_static']
html_favicon = '_static/favicon.ico'
html_logo = '_static/werkzeug.png'
html_show_sourcelink = False

# LaTeX ----------------------------------------------------------------

latex_documents = [
    (master_doc, 'Werkzeug.tex', 'Werkzeug Documentation', author, 'manual'),
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
