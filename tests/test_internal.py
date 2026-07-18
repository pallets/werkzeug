import pytest

from werkzeug._internal import _plain_int
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


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

    response = Response(["Hällo Wörld"])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" in headers

    response = Response(["Hällo Wörld".encode()])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" in headers


@pytest.mark.parametrize(
    ("value", "base", "expect"),
    [
        ("123", 10, 123),
        ("-123", 10, -123),
        ("1_23", 10, None),
        ("+123", 10, None),
        ("𝟙𝟚𝟛", 10, None),
        ("7B", 10, None),
        ("7B", 16, 123),
        ("-7B", 16, -123),
        ("7b", 16, 123),
    ],
)
def test_plain_int(value: str, base: int, expect: int | None) -> None:
    if expect is None:
        with pytest.raises(ValueError):
            _plain_int(value, base)
    else:
        assert _plain_int(value, base) == expect
