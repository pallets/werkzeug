# -*- coding: utf-8 -*-


def test_old_imports():
    """Make sure everything imports from old places"""
    from werkzeug.utils import Headers, MultiDict, CombinedMultiDict, \
         Headers, EnvironHeaders, create_environ, run_wsgi_app
    from werkzeug.http import Accept, MIMEAccept, CharsetAccept, \
         LanguageAccept, ETags, HeaderSet, WWWAuthenticate, \
         Authorization
