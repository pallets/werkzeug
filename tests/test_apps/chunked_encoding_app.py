from werkzeug.wrappers import Request


def app(environ, start_response):
    assert environ["HTTP_TRANSFER_ENCODING"] == "chunked"
    assert environ.get("wsgi.input_terminated", False)
    request = Request(environ)
    assert request.mimetype == "multipart/form-data"
    assert request.files["file"].read() == b"This is a test\n"
    assert request.form["type"] == "text/plain"
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"YES"]
