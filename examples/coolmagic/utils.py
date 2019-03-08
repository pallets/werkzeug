# -*- coding: utf-8 -*-
"""
    coolmagic.utils
    ~~~~~~~~~~~~~~~

    This module contains the subclasses of the base request and response
    objects provided by werkzeug. The subclasses know about their charset
    and implement some additional functionallity like the ability to link
    to view functions.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from os.path import dirname
from os.path import join

from jinja2 import Environment
from jinja2 import FileSystemLoader
from werkzeug.local import Local
from werkzeug.local import LocalManager
from werkzeug.wrappers import BaseRequest
from werkzeug.wrappers import BaseResponse


local = Local()
local_manager = LocalManager([local])
template_env = Environment(
    loader=FileSystemLoader(join(dirname(__file__), "templates"), use_memcache=False)
)
exported_views = {}


def export(string, template=None, **extra):
    """
    Decorator for registering view functions and adding
    templates to it.
    """

    def wrapped(f):
        endpoint = (f.__module__ + "." + f.__name__)[16:]
        if template is not None:
            old_f = f

            def f(**kwargs):
                rv = old_f(**kwargs)
                if not isinstance(rv, Response):
                    rv = TemplateResponse(template, **(rv or {}))
                return rv

            f.__name__ = old_f.__name__
            f.__doc__ = old_f.__doc__
        exported_views[endpoint] = (f, string, extra)
        return f

    return wrapped


def url_for(endpoint, **values):
    """
    Build a URL
    """
    return local.request.url_adapter.build(endpoint, values)


class Request(BaseRequest):
    """
    The concrete request object used in the WSGI application.
    It has some helper functions that can be used to build URLs.
    """

    charset = "utf-8"

    def __init__(self, environ, url_adapter):
        BaseRequest.__init__(self, environ)
        self.url_adapter = url_adapter
        local.request = self


class ThreadedRequest(object):
    """
    A pseudo request object that always poins to the current
    context active request.
    """

    def __getattr__(self, name):
        if name == "__members__":
            return [x for x in dir(local.request) if not x.startswith("_")]
        return getattr(local.request, name)

    def __setattr__(self, name, value):
        return setattr(local.request, name, value)


class Response(BaseResponse):
    """
    The concrete response object for the WSGI application.
    """

    charset = "utf-8"
    default_mimetype = "text/html"


class TemplateResponse(Response):
    """
    Render a template to a response.
    """

    def __init__(self, template_name, **values):
        from coolmagic import helpers

        values.update(request=local.request, h=helpers)
        template = template_env.get_template(template_name)
        Response.__init__(self, template.render(values))
