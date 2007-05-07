# -*- coding: utf-8 -*-
"""
    werkzeug.debug.render
    ~~~~~~~~~~~~~~~~~~~~~

    Render the traceback debugging page.

    :copyright: 2007 by Georg Brandl, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pprint

from werkzeug.minitmpl import Template
from werkzeug.debug.util import Namespace
from werkzeug.debug.templates import HEADER, BODY, CODETABLE, VARTABLE


t_body = Template(BODY)
t_codetable = Template(CODETABLE)
t_vartable = Template(VARTABLE)


def code_table(frame):
    lines = []
    lineno = frame['context_lineno']
    if lineno is not None:
        lineno += 1
        for l in frame['pre_context']:
            lines.append(Namespace(mode='pre', lineno=lineno, code=l))
            lineno += 1
        lines.append(Namespace(mode='cur', lineno=lineno, code=frame['context_line']))
        lineno += 1
        for l in frame['post_context']:
            lines.append(Namespace(mode='post', lineno=lineno, code=l))
            lineno += 1
    else:
        lines.append(Namespace(mode='cur', lineno=1, code='Sourcecode not available'))

    return t_codetable.render(lines=lines)


def var_table(var):
    def safe_pformat(x):
        try:
            return pprint.pformat(x)
        except:
            return '?'

    # dicts
    if isinstance(var, dict) or hasattr(var, 'items'):
        value = var.items()
        if not value:
            typ = 'empty'
        else:
            typ = 'dict'
            value.sort()
            value = [(repr(key), safe_pformat(val)) for key, val in value]

    # lists
    elif isinstance(var, list):
        if not var:
            typ = 'empty'
        else:
            typ = 'list'
            value = [safe_pformat(item) for item in var]

    # others
    else:
        typ = 'simple'
        value = repr(var)

    return t_vartable.render(type=typ, value=value)


def debug_page(context):
    tc = context.to_dict()
    tc['var_table'] = var_table
    tc['code_table'] = code_table
    return HEADER + t_body.render(tc)
