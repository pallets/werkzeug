# -*- coding: utf-8 -*-
"""
    Secure Cookie Example
    ~~~~~~~~~~~~~~~~~~~~~

    Stores session on the client.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from time import asctime

from werkzeug.contrib.securecookie import SecureCookie
from werkzeug.serving import run_simple
from werkzeug.wrappers import BaseRequest
from werkzeug.wrappers import BaseResponse

SECRET_KEY = "V\x8a$m\xda\xe9\xc3\x0f|f\x88\xbccj>\x8bI^3+"


class Request(BaseRequest):
    def __init__(self, environ):
        BaseRequest.__init__(self, environ)
        self.session = SecureCookie.load_cookie(self, secret_key=SECRET_KEY)


def index(request):
    return '<a href="set">Set the Time</a> or <a href="get">Get the time</a>'


def get_time(request):
    return "Time: %s" % request.session.get("time", "not set")


def set_time(request):
    request.session["time"] = time = asctime()
    return "Time set to %s" % time


def application(environ, start_response):
    request = Request(environ)
    response = BaseResponse(
        {"get": get_time, "set": set_time}.get(request.path.strip("/"), index)(request),
        mimetype="text/html",
    )
    request.session.save_cookie(response)
    return response(environ, start_response)


if __name__ == "__main__":
    run_simple("localhost", 5000, application)
