import datetime as dt

import pytest
from markupsafe import escape
from markupsafe import Markup

from werkzeug import exceptions
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.wrappers import Response


def test_override_response() -> None:
    response = Response("Hello, World!")
    error = exceptions.NotFound(response=response)
    assert error.get_response() is response


def test_abort_response() -> None:
    response = Response("Hello, World!")

    with pytest.raises(exceptions.HTTPException) as info:
        exceptions.abort(response)

    assert type(info.value) is exceptions.HTTPException
    assert info.value.get_response() is response


def test_abort_args() -> None:
    with pytest.raises(exceptions.MethodNotAllowed) as exc_info:
        exceptions.abort(405, ["GET", "HEAD"])

    response = exc_info.value.get_response()
    assert response.status_code == 405
    assert response.allow == {"GET", "HEAD"}  # type: ignore[comparison-overlap]


def test_abort_kwargs() -> None:
    with pytest.raises(exceptions.NotFound) as exc_info:
        exceptions.abort(404, description="Not There")

    assert "Not There" in exc_info.value.get_response().get_data(as_text=True)


def test_description_markup() -> None:
    error = exceptions.BadRequest(Markup("<b>&lt;</b>"))
    assert "<b>&lt;</b>" in error.get_response().get_data(as_text=True)


def test_aborter() -> None:
    aborter = exceptions.Aborter({1: exceptions.NotFound})

    with pytest.raises(LookupError):
        aborter(404)

    with pytest.raises(exceptions.NotFound):
        aborter(1)


def test_aborter_extra() -> None:
    aborter = exceptions.Aborter(extra={1: exceptions.NotFound})

    with pytest.raises(exceptions.NotFound):
        aborter(404)

    with pytest.raises(exceptions.NotFound):
        aborter(1)


def test_default_repr() -> None:
    error = exceptions.NotFound()
    assert str(error) == "404 Not Found: The requested resource does not exist."
    assert repr(error) == "<NotFound '404 Not Found'>"


def test_description_repr() -> None:
    error = exceptions.NotFound("Not There")
    assert str(error) == "404 Not Found: Not There"
    assert repr(error) == "<NotFound '404 Not Found'>"


def test_method_not_allowed() -> None:
    response = exceptions.MethodNotAllowed(["GET", "HEAD", "POST"]).get_response()
    assert response.allow == {"GET", "HEAD", "POST"}  # type: ignore[comparison-overlap]


def test_unauthorized() -> None:
    basic = WWWAuthenticate("basic", {"realm": "test"})
    digest = WWWAuthenticate("digest", {"realm": "test", "nonce": "test"})

    error = exceptions.Unauthorized(www_authenticate=basic)
    assert error.get_response().headers["WWW-Authenticate"] == str(basic)

    error = exceptions.Unauthorized(www_authenticate=[digest, basic])
    assert error.get_response().headers.getlist("WWW-Authenticate") == [
        str(digest),
        str(basic),
    ]

    error = exceptions.Unauthorized()
    assert "WWW-Authenticate" not in error.get_response().headers


def test_requested_range_not_satisfiable() -> None:
    error = exceptions.RequestedRangeNotSatisfiable(100)
    assert error.get_response().content_range.length == 100


def test_too_many_requests() -> None:
    error = exceptions.TooManyRequests(retry_after=20)
    assert error.get_response().retry_after is not None


def test_service_unavailable() -> None:
    value = dt.datetime(2020, 1, 4, 18, 52, 16, tzinfo=dt.UTC)
    error = exceptions.ServiceUnavailable(retry_after=value)
    assert error.get_response().retry_after == value


@pytest.mark.parametrize(
    "cls",
    sorted(
        (e for e in exceptions.default_exceptions.values()),
        key=lambda e: e.code,  # type: ignore[attr-defined]
    ),
)
def test_default_response(cls: type[exceptions.HTTPException]) -> None:
    error = cls()
    response = error.get_response()
    body = response.get_data(as_text=True)
    assert response.status_code == error.code
    assert response.content_type == "text/html; charset=utf-8"
    assert body.startswith("<!doctype html>\n<html lang=en>")
    assert f"{error.code} {escape(error.name)}" in body
    assert escape(error.description) in body
