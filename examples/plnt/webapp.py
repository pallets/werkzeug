# -*- coding: utf-8 -*-
"""
    plnt.webapp
    ~~~~~~~~~~~

    The web part of the planet.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from os import path

from sqlalchemy import create_engine
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator

from . import views  # noqa: F401
from .database import metadata
from .database import session
from .utils import endpoints
from .utils import local
from .utils import local_manager
from .utils import url_map

#: path to shared data
SHARED_DATA = path.join(path.dirname(__file__), "shared")


class Plnt(object):
    def __init__(self, database_uri):
        self.database_engine = create_engine(database_uri)

        self._dispatch = local_manager.middleware(self.dispatch_request)
        self._dispatch = SharedDataMiddleware(self._dispatch, {"/shared": SHARED_DATA})

    def init_database(self):
        metadata.create_all(self.database_engine)

    def bind_to_context(self):
        local.application = self

    def dispatch_request(self, environ, start_response):
        self.bind_to_context()
        local.request = request = Request(environ, start_response)
        local.url_adapter = adapter = url_map.bind_to_environ(environ)
        try:
            endpoint, values = adapter.match(request.path)
            response = endpoints[endpoint](request, **values)
        except HTTPException as e:
            response = e
        return ClosingIterator(response(environ, start_response), session.remove)

    def __call__(self, environ, start_response):
        return self._dispatch(environ, start_response)
