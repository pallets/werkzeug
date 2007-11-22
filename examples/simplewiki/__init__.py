# -*- coding: utf-8 -*-
"""
    simplewiki
    ~~~~~~~~~~

    Very simple wiki application based on Genshi, Werkzeug and SQLAlchemy.
    Additionally the creoleparser is used for the wiki markup.

    This example application requires Python 2.4 or higher, primarly beacause
    the creoleparser requires Python 2.4 .  Additionally the code uses some
    decorators or generator expressions.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: BSD.
"""
from simplewiki.application import SimpleWiki
