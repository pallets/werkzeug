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


class Plnt:
    def __init__(self, database_uri):
        self.database_engine = create_engine(database_uri)
        self._full_app = SharedDataMiddleware(self._dispatch, {"/shared": SHARED_DATA})

    def init_database(self):
        metadata.create_all(self.database_engine)

    def bind_to_context(self):
        local.application = self

    def _teardown(self):
        session.remove()
        local_manager.cleanup()

    @Request.application
    def app(self, request):
        try:
            self.bind_to_context()
            local.request = request
            local.url_adapter = url_map.bind_to_environ(request)
            endpoint, values = local.url_adapter.match()
            response = endpoints[endpoint](request, **values)
        except:
            self._teardown()
            raise

        response.call_on_close(self._teardown)
        return response

    def __call__(self, environ, start_response):
        return self._full_app(environ, start_response)
