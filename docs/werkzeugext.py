# -*- coding: utf-8 -*-
"""
    Werkzeug Sphinx Extensions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Provides some more helpers for the werkzeug docs.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from docutils import nodes
from docutils.statemachine import ViewList
from sphinx.util.docstrings import prepare_docstring
from werkzeug import import_string


def parse_rst(state, content_offset, doc):
    node = nodes.section()
    # hack around title style bookkeeping
    surrounding_title_styles = state.memo.title_styles
    surrounding_section_level = state.memo.section_level
    state.memo.title_styles = []
    state.memo.section_level = 0
    state.nested_parse(doc, content_offset, node, match_titles=1)
    state.memo.title_styles = surrounding_title_styles
    state.memo.section_level = surrounding_section_level
    return node.children


def werkzeug_docstring(dirname, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
    env = state.document.settings.env
    name = arguments[0]
    mod = None
    if '.' in name:
        mod, name = name.rsplit('.', 1)
    elif hasattr(env, 'autodoc_current_module'):
        mod = env.autodoc_current_module
    if not mod:
        mod = env.currmodule
    if arguments[0] == '.':
        name = str(mod)
    else:
        name = str((mod and mod + '.' or '') + name)
    doc = ViewList()
    lines = prepare_docstring(import_string(name).__doc__)
    if len(arguments) == 2:
        lines = eval('lines' + arguments[1])
    for line in lines:
        doc.append(line.rstrip().decode('utf-8'), '<werkzeugext>')
    return parse_rst(state, content_offset, doc)


def werkzeug_changelog(dirname, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
    doc = ViewList()
    lines = file('../CHANGES').read().splitlines()[3:]
    for line in lines:
        doc.append(line.rstrip().decode('utf-8'), '<werkzeugext>')
    return parse_rst(state, content_offset, doc)


def setup(app):
    app.add_directive('docstring', werkzeug_docstring, 1, (1, 1, 1))
    app.add_directive('changelog', werkzeug_changelog, 0, (0, 0, 0))
