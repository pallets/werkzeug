from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


@Request.application
def application(request):
    return Response("Hello, World!")


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    run_simple("localhost", 8080, application)
