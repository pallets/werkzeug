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
        """Load and render a tempalte into a unicode string."""
        try:
            template_name, args = args[0], args[1:]
        except IndexError:
            raise TypeError('name of template required')
        return self.get_template(template_name).render(*args, **kwargs)
