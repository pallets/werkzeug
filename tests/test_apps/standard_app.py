import json

from werkzeug.wrappers import BaseResponse as Response


def app(environ, start_response):
    if environ["PATH_INFO"] == "/crash=True":
        1 / 0
    response_body = {key: str(value) for (key, value) in environ.items()}
    response = Response(json.dumps(response_body), mimetype="text/plain")
    return response(environ, start_response)
