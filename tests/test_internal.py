from warnings import filterwarnings
from warnings import resetwarnings

import pytest

from werkzeug import _internal as internal
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


def test_easteregg():
    req = Request.from_values("/?macgybarchakku")
    resp = Response.force_type(internal._easteregg(None), req)
    assert b"About Werkzeug" in resp.get_data()
    assert b"the Swiss Army knife of Python web development" in resp.get_data()


def test_wrapper_internals():
    req = Request.from_values(data={"foo": "bar"}, method="POST")
    req._load_form_data()
    assert req.form.to_dict() == {"foo": "bar"}

    # second call does not break
    req._load_form_data()
    assert req.form.to_dict() == {"foo": "bar"}

    # check reprs
    assert repr(req) == "<Request 'http://localhost/' [POST]>"
    resp = Response()
    assert repr(resp) == "<Response 0 bytes [200 OK]>"
    resp.set_data("Hello World!")
    assert repr(resp) == "<Response 12 bytes [200 OK]>"
    resp.response = iter(["Test"])
    assert repr(resp) == "<Response streamed [200 OK]>"

    # string data does not set content length
    response = Response(["Hällo Wörld"])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" not in headers

    response = Response(["Hällo Wörld".encode()])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" in headers

    # check for internal warnings
    filterwarnings("error", category=Warning)
    response = Response()
    environ = create_environ()
    response.response = "What the...?"
    pytest.raises(Warning, lambda: list(response.iter_encoded()))
    pytest.raises(Warning, lambda: list(response.get_app_iter(environ)))
    response.direct_passthrough = True
    pytest.raises(Warning, lambda: list(response.iter_encoded()))
    pytest.raises(Warning, lambda: list(response.get_app_iter(environ)))
    resetwarnings()
