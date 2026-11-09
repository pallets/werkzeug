import os
import sys

from werkzeug import _reloader
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response

if "TOX_ENV_DIR" in os.environ:
    # tox's layout combined with the default ignores will cause real_app to be
    # ignored. Patch the reloader to avoid this.
    _reloader._stat_ignore_scan = tuple(
        set(_reloader._stat_ignore_scan) - {sys.prefix, sys.exec_prefix}
    )
    _reloader._ignore_common_dirs.discard(".tox")


@Request.application
def app(request):
    import real_app  # type: ignore

    return Response.from_app(real_app.app, request.environ)


kwargs = {"use_reloader": True, "reloader_interval": 0.1}
