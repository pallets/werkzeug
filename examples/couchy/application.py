from couchdb.client import Server
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator

from . import views
from .models import URL
from .utils import local
from .utils import local_manager
from .utils import STATIC_PATH
from .utils import url_map


class Couchy:
    def __init__(self, db_uri):
        local.application = self
        server = Server(db_uri)

        try:
            URL.db = server.create("urls")
        except Exception:
            URL.db = server["urls"]

        self._full_app = SharedDataMiddleware(self.app, {"/static": STATIC_PATH})

    def _teardown(self):
        local_manager.cleanup()

    @Request.application
    def app(self, request):
        try:
            local.application = self
            local.url_adapter = url_map.bind_to_environ(request)
            endpoint, values = local.url_adapter.match()
            handler = getattr(views, endpoint)
            response = handler(request, **values)
        except NotFound:
            response = views.not_found(request)
            response.status_code = 404
        except:
            self._teardown()
            raise

        response.call_on_close(self._teardown)
        return response

    def __call__(self, environ, start_response):
        return self._full_app(environ, start_response)
