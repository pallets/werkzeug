# -*- coding: utf-8 -*-
"""
    coolmagic.helpers
    ~~~~~~~~~~~~~~~~~

    The star-import module for all views.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from coolmagic.utils import Response, TemplateResponse, ThreadedRequest, \
     export, url_for, redirect
from werkzeug.utils import escape


#: a thread local proxy request object
request = ThreadedRequest()
del ThreadedRequest
