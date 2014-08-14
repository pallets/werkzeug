# -*- coding: utf-8 -*-
"""
    tests.compat
    ~~~~~~~~~~~~

    Ensure that old stuff does not break on update.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import warnings
from tests import WerkzeugTests

from werkzeug.wrappers import Response
from werkzeug.test import create_environ


class TestCompat(WerkzeugTests):

    def test_old_imports(self):
        from werkzeug.utils import Headers, MultiDict, CombinedMultiDict, \
             Headers, EnvironHeaders
        from werkzeug.http import Accept, MIMEAccept, CharsetAccept, \
             LanguageAccept, ETags, HeaderSet, WWWAuthenticate, \
             Authorization

    def test_exposed_werkzeug_mod(self):
        import werkzeug
        for key in werkzeug.__all__:
            # deprecated, skip it
            if key in ('templates', 'Template'):
                continue
            getattr(werkzeug, key)
