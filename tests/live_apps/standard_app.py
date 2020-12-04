import json

from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


@Request.application
def app(request):
    if request.path == "/crash":
        raise Exception("crash requested")

    return Response(
        json.dumps(request.environ, default=lambda x: str(x)),
        content_type="application/json",
    )
