# -*- coding: <%= FILE_ENCODING %> -*-
<%= make_docstring(MODULE, '''\
This module provides the WSGI application. It connects the URL map
from `%(PACKAGE)s.urls` to the views defined in `%(PACKAGE)s.views`.
The actual request and response objects are part of the
`%(PACKAGE)s.utils` module and should be imported from there in order
to avoid circular import dependencies.

The WSGI middlewares are applied in the `make_app` factory function that
automatically wraps the application within the require middlewares. Per
default only the `SharedDataMiddleware` is applied.''' % globals()) %>
import os
from <%= PACKAGE %>.urls import url_map, not_found
from <%= PACKAGE %>.utils import Request, Response, RedirectResponse
from <%= PACKAGE %>.views import get_view
from werkzeug.utils import SharedDataMiddleware
from werkzeug.routing import NotFound, RequestRedirect


class <%= PACKAGE_PASCAL_CASED %>Application(object):
    """
    The application class. It's passed a directory with configuration values.
    """

    def __init__(self, config):
        self.config = config

    def __call__(self, environ, start_response):
        url_adapter = url_map.bind_to_environ(environ)
        req = Request(environ, url_adapter)
        try:
            endpoint, args = url_adapter.match(req.path)
        except NotFound:
            resp = get_view(not_found)(req)
        except RequestRedirect, e:
            resp = RedirectResponse(e.new_url)
        else:
            resp = get_view(endpoint)(req, **args)
        return resp(environ, start_response)


def make_app(config=None):
    """
    Factory function that creates a new `<%= PACKAGE_PASCAL_CASED %>Application`
    object. Optional WSGI middlewares should be applied here.
    """
    app = <%= PACKAGE_PASCAL_CASED %>Application(config or {})
    app = SharedDataMiddleware(app, {
        '/public': os.path.join(os.path.dirname(__file__), 'public')
    })
    return app
