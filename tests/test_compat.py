# -*- coding: utf-8 -*-
"""
    tests.compat
    ~~~~~~~~~~~~

    Ensure that old stuff does not break on update.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""

# This file shouldn't be linted:
# flake8: noqa

import warnings

from werkzeug.wrappers import Response
from werkzeug.test import create_environ


def test_old_imports():
    from werkzeug.utils import Headers, MultiDict, CombinedMultiDict, \
        Headers, EnvironHeaders
    from werkzeug.http import Accept, MIMEAccept, CharsetAccept, \
        LanguageAccept, ETags, HeaderSet, WWWAuthenticate, \
        Authorization


def test_exposed_werkzeug_mod():
    import werkzeug
    for key in werkzeug.__all__:
        getattr(werkzeug, key)
