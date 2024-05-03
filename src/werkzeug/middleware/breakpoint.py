from __future__ import annotations

import collections.abc as c
import traceback
import typing as t

from ..exceptions import InternalServerError

if t.TYPE_CHECKING:
    from _typeshed.wsgi import StartResponse
    from _typeshed.wsgi import WSGIApplication
    from _typeshed.wsgi import WSGIEnvironment


class BreakpointWSGIMiddleware:
    """Call Python's :func:`breakpoint` function to drop into a debugger on
    unhandled exceptions. Python's default debugger is :mod:`pdb`, but there are
    others available, such as in IDEs.

    :param app: The WSGI application to wrap.
    """

    def __init__(self, app: WSGIApplication) -> None:
        self.app = app

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> c.Iterable[bytes]:
        app_iter: c.Iterable[bytes] | None = None

        try:
            app_iter = self.app(environ, start_response)
            yield from app_iter

            if hasattr(app_iter, "close"):
                app_iter.close()
        except Exception:
            if app_iter is not None and hasattr(app_iter, "close"):
                app_iter.close()

            app_iter = InternalServerError()(environ, start_response)

            try:
                yield from app_iter
            except Exception:
                # If a streaming response raised part way through the real
                # app_iter, the headers were already sent and the 500 error
                # can't be sent in its place.
                pass

            traceback.print_exc(file=environ["wsgi.errors"])
            breakpoint()
