# -*- coding: utf-8 -*-
"""
    werkzeug.debug.utils
    ~~~~~~~~~~~~~~~~~~~~

    Various other utilities.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
from os.path import join, dirname
from werkzeug.templates import Template


def get_template(filename):
    return Template.from_file(join(dirname(__file__), 'templates', filename))


def render_template(template_filename, **context):
    return get_template(template_filename).render(**context)
