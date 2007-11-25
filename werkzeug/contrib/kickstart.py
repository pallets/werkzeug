# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.kickstart
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides some simple shortcuts to make using Werkzeug
    simpler for small scripts.


    :copyright: 2007 by Marek Kubica, Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from os import path
from werkzeug.wrappers import BaseRequest, BaseResponse
from werkzeug.templates import Template


__all__ = ['Request', 'Response', 'TemplateNotFound', 'TemplateLoader']


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


class TemplateNotFound(IOError, LookupError):
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

    def __init__(self, search_path, encoding='utf-8'):
        self.search_path = path.abspath(search_path)
        self.encoding = encoding

    def get_template(self, name):
        """Get a template from a given name."""
        filename = path.join(self.search_path, *[p for p in name.split('/')
                                                 if p and p[0] != '.'])
        if not path.exists(filename):
            raise TemplateNotFound(name)
        return Template.from_file(filename, self.encoding)

    def render_to_response(self, *args, **kwargs):
        """Load and render a template into a response object."""
        return Response(self.render_to_string(*args, **kwargs))

    def render_to_string(self, *args, **kwargs):
        """Load and render a tempalte into a unicode string."""
        try:
            template_name, args = args[0], args[1:]
        except IndexError:
            raise TypeError('name of template required')
        return self.get_template(template_name).render(*args, **kwargs)
