# -*- coding: utf-8 -*-
"""
    cupoftee.application
    ~~~~~~~~~~~~~~~~~~~~

    The WSGI appliction for the cup of tee browser.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import time
from os import path
from threading import Thread
from cupoftee.db import Database
from cupoftee.network import ServerBrowser
from werkzeug.templates import Template
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.routing import Map, Rule


templates = path.join(path.dirname(__file__), 'templates')
pages = {}
url_map = Map([Rule('/shared/<file>', endpoint='shared')])


def make_app(database, interval=60):
    return SharedDataMiddleware(Cup(database), {
        '/shared':  path.join(path.dirname(__file__), 'shared')
    })


class PageMeta(type):

    def __init__(cls, name, bases, d):
        type.__init__(cls, name, bases, d)
        if d.get('url_rule') is not None:
            pages[cls.identifier] = cls
            url_map.add(Rule(cls.url_rule, endpoint=cls.identifier,
                             **cls.url_arguments))

    identifier = property(lambda x: x.__name__.lower())


class Page(object):
    __metaclass__ = PageMeta
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
            template = self.__class__.identifier + '.html'
        context = dict(self.__dict__)
        context.update(url_for=self.url_for, self=self)
        body_tmpl = Template.from_file(path.join(templates, template))
        layout_tmpl = Template.from_file(path.join(templates, 'layout.html'))
        context['body'] = body_tmpl.render(context)
        return layout_tmpl.render(context)

    def get_response(self):
        return Response(self.render_template(), mimetype='text/html')


class Cup(object):

    def __init__(self, database, interval=120):
        self.interval = interval
        self.db = Database(database)
        self.master = ServerBrowser(self)
        self.updater = Thread(None, self.update_master)
        self.updater.setDaemon(True)
        self.updater.start()

    def update_master(self):
        wait = self.interval
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
        except NotFound, e:
            page = MissingPage(self, request, url_adapter)
            response = page.process()
        except HTTPException, e:
            return e
        return response or page.get_response()

    def __call__(self, environ, start_response):
        request = Request(environ)
        return self.dispatch_request(request)(environ, start_response)


from cupoftee.pages import MissingPage
