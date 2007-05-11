# -*- coding: <%= FILE_ENCODING %> -*-
from <%= PACKAGE %>.urls import url_map, not_found
from <%= PACKAGE %>.utils import Request, Response, RedirectResponse
from <%= PACKAGE %>.views import get_view
from werkzeug.routing import NotFound, RequestRedirect


class <%= PACKAGE_PASCAL_CASED %>Application(object):

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
    app = <%= PACKAGE_PASCAL_CASED %>Application(config or {})
    return app
