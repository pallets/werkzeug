from couchdb.client import Server
from couchy.utils import STATIC_PATH, local, local_manager, \
     url_map
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator, SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from couchy import views
from couchy.models import URL
import couchy.models


class Couchy(object):

    def __init__(self, db_uri):
        local.application = self

        server = Server(db_uri)
        try:
            db = server.create('urls')
        except:
            db = server['urls']
        self.dispatch = SharedDataMiddleware(self.dispatch, {
            '/static':    STATIC_PATH
        })

        URL.db = db

    def dispatch(self, environ, start_response):
        local.application = self
        request = Request(environ)
        local.url_adapter = adapter = url_map.bind_to_environ(environ)
        try:
            endpoint, values = adapter.match()
            handler = getattr(views, endpoint)
            response = handler(request, **values)
        except NotFound, e:
            response = views.not_found(request)
            response.status_code = 404
        except HTTPException, e:
            response = e
        return ClosingIterator(response(environ, start_response),
                                [local_manager.cleanup])

    def __call__(self, environ, start_response):
        return self.dispatch(environ, start_response)
