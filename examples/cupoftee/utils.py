# -*- coding: utf-8 -*-
"""
    cupoftee.utils
    ~~~~~~~~~~~~~~

    Various utilities.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re


_sort_re = re.compile(r'\w+(?u)')


def unicodecmp(a, b):
    x, y = map(_sort_re.search, [a, b])
    return cmp((x and x.group() or a).lower(), (y and y.group() or b).lower())
