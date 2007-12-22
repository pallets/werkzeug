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

__all__ = ['Request', 'Response', 'TemplateNotFound', 'TemplateLoader',
        'GenshiTemplateLoader']


class Request(BaseRequest):
    """
    A handy subclass of the base request that adds a URL builder.
    It when supplied a session store, it is also able to handle sessions.
    """

    def __init__(self, environ, url_map,
            session_store=None, cookie_name=None):
        # call the parent for initialization
        BaseRequest.__init__(self, environ)
        # create an adapter
        self.url_adapter = url_map.bind_to_environ(environ)
        # create all stuff for sessions
        self.session_store = session_store
        self.cookie_name = cookie_name

        if session_store is not None and cookie_name is not None:
            if cookie_name in self.cookies:
                # get the session out of the storage
                self.session = session_store.get(self.cookies[cookie_name])
            else:
                # create a new session
                self.session = session_store.new()

    def url_for(self, callback, **values):
        return self.url_adapter.build(callback, values)


class Response(BaseResponse):
    """
    A subclass of base response which sets the default mimetype to text/html.
    It the `Request` that came in is using Werkzeug sessions, this class
    takes care of saving that session.
    """
    default_mimetype = 'text/html'

    def __call__(self, environ, start_response):
        # get the request object
        request = environ['werkzeug.request']

        if request.session_store is not None:
            # save the session if neccessary
            request.session_store.save_if_modified(request.session)

            # set the cookie for the browser if it is not there:
            if request.cookie_name not in request.cookies:
                self.set_cookie(request.cookie_name, request.session.sid)

        # go on with normal response business
        return BaseResponse.__call__(self, environ, start_response)


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
        """Load and render a template into a unicode string."""
        try:
            template_name, args = args[0], args[1:]
        except IndexError:
            raise TypeError('name of template required')
        return self.get_template(template_name).render(*args, **kwargs)


class GenshiTemplateLoader(TemplateLoader):
    """
    A unified interface for loading Genshi templates. Actually a quite thin
    wrapper for Genshi's TemplateLoader.

    It sets some defaults that differ from the Genshi loader, most notably
    auto_reload is active. All imporant options can be passed through to
    Genshi.
    The default output type is 'html', but can be adjusted easily by changing
    the `output_type` attribute.
    """
    def __init__(self, search_path, encoding='utf-8', **kwargs):
        TemplateLoader.__init__(self, search_path, encoding)
        # import Genshi here, because we don't want a general Genshi
        # dependency, only a local one
        from genshi.template import TemplateLoader as GenshiLoader
        from genshi.template.loader import TemplateNotFound

        self.not_found_exception = TemplateNotFound
        # set auto_reload to True per default
        reload_template = kwargs.pop('auto_reload', True)
        # get rid of default_encoding as this template loaders overwrites it
        # with the value of encoding
        kwargs.pop('default_encoding', None)

        # now, all arguments are clean, pass them on
        self.loader = GenshiLoader(search_path, default_encoding=encoding,
                auto_reload=reload_template, **kwargs)

        # the default output is HTML but can be overridden easily
        self.output_type = 'html'
        self.encoding = encoding

    def get_template(self, template_name):
        """Get the template which is at the given name"""
        try:
            return self.loader.load(template_name, encoding=self.encoding)
        except self.not_found_exception, e:
            # catch the exception raised by Genshi, convert it into a werkzeug
            # exception (for the sake of consistency)
            raise TemplateNotFound(template_name)

    def render_to_string(self, template_name, context=None):
        """Load and render a template into an unicode string"""
        # create an empty context if no context was specified
        context = context or {}
        tmpl = self.get_template(template_name)
        # render the template into a unicode string (None means unicode)
        return tmpl.\
            generate(**context).\
            render(self.output_type, encoding=None)
