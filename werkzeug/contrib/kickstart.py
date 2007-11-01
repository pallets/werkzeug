# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.kickstart
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides some simple shortcuts to make using Werkzeug simpler.

    :copyright: 2007 by Marek Kubica.
    :license: BSD, see LICENSE for more details.
"""
from os import path
import codecs
from werkzeug.wrappers import BaseRequest, BaseResponse
from werkzeug.minitmpl import Template


__all__ = ['Request', 'Response', 'TemplateNotFound', 'TemplateLoader',
           'TemplateResponse']


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


class TemplateNotFound(IOError, RuntimeError):
    """
    A template was not found by the template loader.
    """

    def __init__(self, name):
        IOError.__init__(self, name)
        self.name = name


class TemplateLoader(object):
    """
    A simple loader interface for the werkzeug minitmpl
    template language.
    """

    def __init__(self, search_path, charset='utf-8'):
        self.search_path = path.abspath(search_path)
        self.charset = charset

    def get_source(self, name):
        """Load and return a files source as a unicode string"""
        filename = path.join(self.search_path, *[p for p in name.split('/')
                                           if p and p[0] != '.'])
        if path.exists(filename):
            f = codecs.open(filename, 'r', self.charset)
            try:
                return f.read()
            finally:
                f.close()
        else:
            raise TemplateNotFound(name)



class TemplateResponse(Response):
    """
    A base class that provides rendering of a minitmpl template to
    a response.

    If no loader is given *template* is interpreted as a template
    source code.
    """

    def __init__(self, template, loader=None, *args, **kwargs):
        if loader is None:
            template = Template(template)
        else:
            template = Template(loader.get_source(template))
        Response.__init__(self, template.render(*args, **kwargs),
                          mimetype='text/html')
