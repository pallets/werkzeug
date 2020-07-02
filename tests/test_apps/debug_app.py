from werkzeug.debug import DebuggedApplication


@DebuggedApplication
def app(environ, start_response):
    if environ["PATH_INFO"] == "/crash=True":
        1 / 0
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"hello"]
