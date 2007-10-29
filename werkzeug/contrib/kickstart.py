# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.kickstart
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides some simple shortcuts to make using Werkzeug simpler.

    :copyright: 2007 by Marek Kubica.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.wrappers import BaseRequest, BaseResponse


class Request(BaseRequest):
    """
    A handy subclass of the base request that adds a URL builder.
    """

    def __init__(self, environ, url_map):
        BaseRequest.__init__(self, environ)
        self.url_adapter = url_map.bind_to_environ(environ)

    def url_for(self, callback, **values):
        return self.url_adapter.build(callback, values)


class Response(BaseResponse):
    """
    A subclass of base response which sets the default mimetype to text/html
    """
    default_mimetype = 'text/html'
