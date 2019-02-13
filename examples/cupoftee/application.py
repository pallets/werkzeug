# -*- coding: utf-8 -*-
"""
    cupoftee.application
    ~~~~~~~~~~~~~~~~~~~~

    The WSGI appliction for the cup of tee browser.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import time
from os import path
from threading import Thread

from jinja2 import Environment
from jinja2 import PackageLoader
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.routing import Map
from werkzeug.routing import Rule
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response

from .db import Database
from .network import ServerBrowser


templates = path.join(path.dirname(__file__), "templates")
pages = {}
url_map = Map([Rule("/shared/<file>", endpoint="shared")])


def make_app(database, interval=120):
    return SharedDataMiddleware(
        Cup(database, interval),
        {"/shared": path.join(path.dirname(__file__), "shared")},
    )


class PageMeta(type):
    def __init__(cls, name, bases, d):
        type.__init__(cls, name, bases, d)
        if d.get("url_rule") is not None:
            pages[cls.identifier] = cls
            url_map.add(
                Rule(cls.url_rule, endpoint=cls.identifier, **cls.url_arguments)
            )

    identifier = property(lambda self: self.__name__.lower())


def _with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""

    class metaclass(type):
        def __new__(metacls, name, this_bases, d):
            return meta(name, bases, d)

    return type.__new__(metaclass, "temporary_class", (), {})


class Page(_with_metaclass(PageMeta, object)):
    url_arguments = {}

    def __init__(self, cup, request, url_adapter):
        self.cup = cup
        self.request = request
        self.url_adapter = url_adapter

    def url_for(self, endpoint, **values):
        return self.url_adapter.build(endpoint, values)

    def process(self):
        pass

    def render_template(self, template=None):
        if template is None:
            template = self.__class__.identifier + ".html"
        context = dict(self.__dict__)
        context.update(url_for=self.url_for, self=self)
        return self.cup.render_template(template, context)

    def get_response(self):
        return Response(self.render_template(), mimetype="text/html")


class Cup(object):
    def __init__(self, database, interval=120):
        self.jinja_env = Environment(loader=PackageLoader("cupoftee"), autoescape=True)
        self.interval = interval
        self.db = Database(database)
        self.master = ServerBrowser(self)
        self.updater = Thread(None, self.update_master)
        self.updater.setDaemon(True)
        self.updater.start()

    def update_master(self):
        while 1:
            if self.master.sync():
                wait = self.interval
            else:
                wait = self.interval // 2
            time.sleep(wait)

    def dispatch_request(self, request):
        url_adapter = url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = url_adapter.match()
            page = pages[endpoint](self, request, url_adapter)
            response = page.process(**values)
        except NotFound:
            page = MissingPage(self, request, url_adapter)
            response = page.process()
        except HTTPException as e:
            return e
        return response or page.get_response()

    def __call__(self, environ, start_response):
        request = Request(environ)
        return self.dispatch_request(request)(environ, start_response)

    def render_template(self, name, **context):
        template = self.jinja_env.get_template(name)
        return template.render(context)


from cupoftee.pages import MissingPage
