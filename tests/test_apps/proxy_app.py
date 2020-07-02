from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


@Request.application
def app(request):
    special = request.headers.get("X-Special")
    host = request.environ["HTTP_HOST"]
    return Response(f"{special}|{host}|{request.full_path}")
