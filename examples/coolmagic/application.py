# -*- coding: utf-8 -*-
"""
    coolmagic.application
    ~~~~~~~~~~~~~~~~~~~~~

     This module provides the WSGI application.

    The WSGI middlewares are applied in the `make_app` factory function
    that automatically wraps the application within the require
    middlewares. Per default only the `SharedDataMiddleware` is applied.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from os import path, listdir
from coolmagic.utils import Request, abort, redirect, DirectResponse
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect


class CoolMagicApplication(object):
    """
    The application class. It's passed a directory with configuration values.
    """

    def __init__(self, config):
        self.config = config

        for fn in listdir(path.join(path.dirname(__file__), 'views')):
            if fn.endswith('.py') and fn != '__init__.py':
                __import__('coolmagic.views.' + fn[:-3])

        from coolmagic.utils import exported_views
        rules = [
            # url for shared data. this will always be unmatched
            # because either the middleware or the webserver
            # handles that request first.
            Rule('/public/<string(allow_slash=True):file>',
                 endpoint='shared_data')
        ]
        self.views = {}
        for endpoint, (func, rule, extra) in exported_views.iteritems():
            rules.append(Rule(rule, endpoint=endpoint, **extra))
            self.views[endpoint] = func
        self.url_map = Map(rules)

    def __call__(self, environ, start_response):
        urls = self.url_map.bind_to_environ(environ)
        req = Request(environ, urls)
        try:
            try:
                endpoint, args = urls.match(req.path)
            except NotFound:
                abort(404)
            except RequestRedirect, e:
                redirect(e.new_url)
            resp = self.views[endpoint](**args)
        except DirectResponse, e:
            resp = e.response
        return resp(environ, start_response)


def make_app(config=None):
    """
    Factory function that creates a new `CoolmagicApplication`
    object. Optional WSGI middlewares should be applied here.
    """
    app = CoolMagicApplication(config or {})

    # static stuff
    from werkzeug.utils import SharedDataMiddleware
    app = SharedDataMiddleware(app, {
        '/public': path.join(path.dirname(__file__), 'public')
    })

    # if we are in debug mode we wrap the application in the debugger
    # middleware provided by werkzeug.
    if config.get('debug', False):
        from werkzeug.debug import DebuggedApplication
        app = DebuggedApplication(app, evalex=config.get('evalex', False))
    return app
