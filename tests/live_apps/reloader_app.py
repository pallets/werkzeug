import os
import sys

from werkzeug import _reloader
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response

# Tox puts the tmp dir in the venv sys.prefix, patch the reloader so
# it doesn't skip real_app.
if "TOX_ENV_DIR" in os.environ:
    _reloader._stat_ignore_scan = tuple(
        set(_reloader._stat_ignore_scan) - {sys.prefix, sys.exec_prefix}
    )


@Request.application
def app(request):
    import real_app  # type: ignore

    return Response.from_app(real_app.app, request.environ)


kwargs = {"use_reloader": True, "reloader_interval": 0.1}
