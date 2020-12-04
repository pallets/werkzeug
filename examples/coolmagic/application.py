"""This module provides the WSGI application.

The WSGI middlewares are applied in the `make_app` factory function that
automatically wraps the application within the require middlewares. Per
default only the `SharedDataMiddleware` is applied.
"""
from os import listdir
from os import path

from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.routing import Map
from werkzeug.routing import RequestRedirect
from werkzeug.routing import Rule

from .utils import local_manager
from .utils import Request


class CoolMagicApplication:
    """
    The application class. It's passed a directory with configuration values.
    """

    def __init__(self, config):
        self.config = config

        for fn in listdir(path.join(path.dirname(__file__), "views")):
            if fn.endswith(".py") and fn != "__init__.py":
                __import__(f"coolmagic.views.{fn[:-3]}")

        from coolmagic.utils import exported_views

        rules = [
            # url for shared data. this will always be unmatched
            # because either the middleware or the webserver
            # handles that request first.
            Rule("/public/<path:file>", endpoint="shared_data")
        ]
        self.views = {}
        for endpoint, (func, rule, extra) in exported_views.items():
            if rule is not None:
                rules.append(Rule(rule, endpoint=endpoint, **extra))
            self.views[endpoint] = func
        self.url_map = Map(rules)

    def __call__(self, environ, start_response):
        urls = self.url_map.bind_to_environ(environ)
        req = Request(environ, urls)
        try:
            endpoint, args = urls.match(req.path)
            resp = self.views[endpoint](**args)
        except NotFound:
            resp = self.views["static.not_found"]()
        except (HTTPException, RequestRedirect) as e:
            resp = e
        return resp(environ, start_response)


def make_app(config=None):
    """
    Factory function that creates a new `CoolmagicApplication`
    object. Optional WSGI middlewares should be applied here.
    """
    config = config or {}
    app = CoolMagicApplication(config)

    # static stuff
    app = SharedDataMiddleware(
        app, {"/public": path.join(path.dirname(__file__), "public")}
    )

    # clean up locals
    app = local_manager.make_middleware(app)

    return app
