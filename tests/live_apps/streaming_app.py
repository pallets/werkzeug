from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


@Request.application
def app(request):
    def gen():
        for x in range(5):
            yield f"{x}\n"

        if request.path == "/crash":
            raise Exception("crash requested")

    return Response(gen())
