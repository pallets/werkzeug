# -*- coding: utf-8 -*-
"""
    coolmagic.helpers
    ~~~~~~~~~~~~~~~~~

    The star-import module for all views.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from coolmagic.utils import Response, TemplateResponse, ThreadedRequest, \
     export, url_for, redirect
from werkzeug import escape


#: a thread local proxy request object
request = ThreadedRequest()
del ThreadedRequest
