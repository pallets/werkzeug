# -*- coding: utf-8 -*-
"""
    coolmagic.utils
    ~~~~~~~~~~~~~~~

    This module contains the subclasses of the base request and response
    objects provided by werkzeug. The subclasses know about their charset
    and implement some additional functionallity like the ability to link
    to view functions.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import threading
from os.path import dirname, join
from jinja import Environment, FileSystemLoader
from werkzeug.wrappers import BaseRequest, BaseResponse


thread_locals = threading.local()

template_env = Environment(
    loader=FileSystemLoader(join(dirname(__file__), 'templates'),
                            use_memcache=False)
)


exported_views = {}
exported_aborts = {}


def export(string, template=None, **extra):
    """
    Decorator for registering view functions and adding
    templates to it.
    """
    def wrapped(f):
        endpoint = (f.__module__ + '.' + f.__name__)[16:]
        if template is not None:
            old_f = f
            def f(**kwargs):
                rv = old_f(**kwargs)
                if not isinstance(rv, Response):
                    rv = TemplateResponse(template, **(rv or {}))
                return rv
            f.__name__ = old_f.__name__
            f.__doc__ = old_f.__doc__
        if isinstance(string, (int, long)):
            exported_aborts[string] = f
        else:
            exported_views[endpoint] = (f, string, extra)
        return f
    return wrapped


def url_for(endpoint, **values):
    """
    Build a URL
    """
    return thread_locals.request.url_adapter.build(endpoint, values)


def abort(code, **args):
    """
    Abort somehow.
    """
    raise DirectResponse(exported_aborts[code](**args))


def redirect(url, code=302):
    """
    Looks nicer than abort.
    """
    abort(code, url=url)


class DirectResponse(Exception):
    """
    Raise this exception to send a response to the wsgi app.
    """

    def __init__(self, response):
        self.response = response
        Exception.__init__(self, response)


class Request(BaseRequest):
    """
    The concrete request object used in the WSGI application.
    It has some helper functions that can be used to build URLs.
    """
    charset = 'utf-8'

    def __init__(self, environ, url_adapter):
        BaseRequest.__init__(self, environ)
        self.url_adapter = url_adapter
        thread_locals.request = self


class ThreadedRequest(object):

    def __getattr__(self, name):
        if name == '__members__':
            return [x for x in dir(thread_locals.request) if not
                    x.startswith('_')]
        return getattr(thread_locals.request, name)

    def __setattr__(self, name, value):
        return setattr(thread_locals.request, name, value)


threaded_request = ThreadedRequest()


class Response(BaseResponse):
    """
    The concrete response object for the WSGI application.
    """
    charset = 'utf-8'
    default_mimetype = 'text/html'


class TemplateResponse(Response):
    """
    Render a template to a response.
    """

    def __init__(self, template_name, **values):
        from coolmagic import helpers
        values.update(
            request=thread_locals.request,
            h=helpers
        )
        template = template_env.get_template(template_name)
        Response.__init__(self, template.render(values))
