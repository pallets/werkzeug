"""This module provides the WSGI application.

The WSGI middlewares are applied in the `make_app` factory function that
automatically wraps the application within the require middlewares. Per
default only the `SharedDataMiddleware` is applied.
"""
from os import listdir
from os import path

from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.routing import Map
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

    def _teardown(self):
        local_manager.cleanup()

    @Request.application
    def __call__(self, request):
        try:
            request.url_adapter = self.url_map.bind_to_environ(request)
            endpoint, args = request.url_adapter.match()
            response = self.views[endpoint](**args)
        except NotFound:
            response = self.views["static.not_found"]()
        except:
            self._teardown()
            raise

        response.call_on_close(self._teardown)
        return response


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
    return app
