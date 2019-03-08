# -*- coding: utf-8 -*-
"""
    simplewiki.application
    ~~~~~~~~~~~~~~~~~~~~~~

    This module implements the wiki WSGI application which dispatches
    requests to specific wiki pages and actions.


    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from os import path

from sqlalchemy import create_engine
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.utils import redirect
from werkzeug.wsgi import ClosingIterator

from . import actions
from .database import metadata
from .database import session
from .specialpages import page_not_found
from .specialpages import pages
from .utils import href
from .utils import local
from .utils import local_manager
from .utils import Request


#: path to shared data
SHARED_DATA = path.join(path.dirname(__file__), "shared")


class SimpleWiki(object):
    """
    Our central WSGI application.
    """

    def __init__(self, database_uri):
        self.database_engine = create_engine(database_uri)

        # apply our middlewares.   we apply the middlewars *inside* the
        # application and not outside of it so that we never lose the
        # reference to the `SimpleWiki` object.
        self._dispatch = SharedDataMiddleware(
            self.dispatch_request, {"/_shared": SHARED_DATA}
        )

        # free the context locals at the end of the request
        self._dispatch = local_manager.make_middleware(self._dispatch)

    def init_database(self):
        """Called from the management script to generate the db."""
        metadata.create_all(bind=self.database_engine)

    def bind_to_context(self):
        """
        Useful for the shell.  Binds the application to the current active
        context.  It's automatically called by the shell command.
        """
        local.application = self

    def dispatch_request(self, environ, start_response):
        """Dispatch an incoming request."""
        # set up all the stuff we want to have for this request.  That is
        # creating a request object, propagating the application to the
        # current context and instanciating the database session.
        self.bind_to_context()
        request = Request(environ)
        request.bind_to_context()

        # get the current action from the url and normalize the page name
        # which is just the request path
        action_name = request.args.get("action") or "show"
        page_name = u"_".join([x for x in request.path.strip("/").split() if x])

        # redirect to the Main_Page if the user requested the index
        if not page_name:
            response = redirect(href("Main_Page"))

        # check special pages
        elif page_name.startswith("Special:"):
            if page_name[8:] not in pages:
                response = page_not_found(request, page_name)
            else:
                response = pages[page_name[8:]](request)

        # get the callback function for the requested action from the
        # action module.  It's "on_" + the action name.  If it doesn't
        # exists call the missing_action method from the same module.
        else:
            action = getattr(actions, "on_" + action_name, None)
            if action is None:
                response = actions.missing_action(request, action_name)
            else:
                response = action(request, page_name)

        # make sure the session is removed properly
        return ClosingIterator(response(environ, start_response), session.remove)

    def __call__(self, environ, start_response):
        """Just forward a WSGI call to the first internal middleware."""
        return self._dispatch(environ, start_response)
