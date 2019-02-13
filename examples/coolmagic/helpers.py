# -*- coding: utf-8 -*-
"""
    coolmagic.helpers
    ~~~~~~~~~~~~~~~~~

    The star-import module for all views.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from .utils import ThreadedRequest


#: a thread local proxy request object
request = ThreadedRequest()
del ThreadedRequest
