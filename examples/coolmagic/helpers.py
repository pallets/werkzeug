# -*- coding: utf-8 -*-
"""
    coolmagic.helpers
    ~~~~~~~~~~~~~~~~~

    The star-import module for all views.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from coolmagic.utils import Response, TemplateResponse, ThreadedRequest, \
     export, url_for, redirect
from werkzeug.utils import escape


#: a thread local proxy request object
request = ThreadedRequest()
del ThreadedRequest
