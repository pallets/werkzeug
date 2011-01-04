from sqlalchemy import create_engine
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator, SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from shorty.utils import STATIC_PATH, session, local, local_manager, \
     metadata, url_map

import shorty.models
from shorty import views


class Shorty(object):

    def __init__(self, db_uri):
        local.application = self
        self.database_engine = create_engine(db_uri, convert_unicode=True)

        self.dispatch = SharedDataMiddleware(self.dispatch, {
            '/static':  STATIC_PATH
        })

    def init_database(self):
        metadata.create_all(self.database_engine)

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
                               [session.remove, local_manager.cleanup])

    def __call__(self, environ, start_response):
        return self.dispatch(environ, start_response)
