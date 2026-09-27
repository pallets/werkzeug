from __future__ import annotations

import datetime as dt

import pytest

from werkzeug.datastructures import ETag
from werkzeug.datastructures.headers import Headers
from werkzeug.datastructures.range import IfRange
from werkzeug.datastructures.range import Range
from werkzeug.exceptions import RequestedRangeNotSatisfiable
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers.response import Response


def make_response(
    *,
    method: str = "GET",
    if_range: IfRange | None = None,
    range: Range | None = None,
    status: int = 200,
    length: int | None = -1,
    etag: ETag | None = None,
    last_modified: dt.datetime | None = None,
) -> Response:
    headers = Headers()

    if if_range is not None:
        headers["If-Range"] = if_range.to_header()

    if range is not None:
        headers["Range"] = range.to_header()

    request = EnvironBuilder(method=method, headers=headers).get_request()
    response = Response("0123456789", status=status)

    if length != -1:
        response.content_length = length

    response.etag = etag
    response.last_modified = last_modified
    response.apply_range(request)
    return response


def test_advertise() -> None:
    response = make_response()
    assert response.status_code == 200
    assert response.accept_ranges == "bytes"
    assert not response.content_range


five = Range("bytes", [(0, 5)])


def test_range() -> None:
    response = make_response(range=five)
    assert response.status_code == 206
    assert response.accept_ranges == "bytes"
    assert response.content_range.to_header() == "bytes 0-4/10"
    assert response.content_length == 5
    assert response.get_data(as_text=True) == "01234"


def test_clamp_stop() -> None:
    response = make_response(range=Range("bytes", [(7, 101)]))
    assert response.content_range.to_header() == "bytes 7-9/10"
    assert response.content_length == 3


def test_clamp_suffix() -> None:
    response = make_response(range=Range("bytes", [(-100, None)]))
    assert response.content_range.to_header() == "bytes 0-9/10"
    assert response.content_length == 10


def test_start_too_large() -> None:
    with pytest.raises(RequestedRangeNotSatisfiable):
        make_response(range=Range("bytes", [(20, None)]))


def test_only_first() -> None:
    response = make_response(range=Range("bytes", [(0, 5), (5, 10)]))
    assert response.content_range.to_header() == "bytes 0-4/10"
    assert response.content_length == 5


def test_precondition_applied() -> None:
    response = make_response(range=five, status=304)
    assert response.status_code == 304


def test_post() -> None:
    response = make_response(method="POST", range=five)
    assert response.status_code == 200


def test_other_unit() -> None:
    response = make_response(range=Range("other", [(0, 5)]))
    assert response.status_code == 200


@pytest.mark.parametrize("length", [None, 0])
def test_no_length(length: int | None) -> None:
    response = make_response(range=five, length=length)
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("etag", "expect"),
    [
        (ETag("a"), 206),
        (ETag("b"), 200),
        (ETag("a", weak=True), 200),
        (None, 200),
    ],
)
def test_if_range_etag(etag: ETag | None, expect: int) -> None:
    response = make_response(range=five, if_range=IfRange(etag="a"), etag=etag)
    assert response.status_code == expect


modified = dt.datetime(2026, 9, 26, 8, 15, tzinfo=dt.UTC)
before = modified - dt.timedelta(days=1)
after = modified + dt.timedelta(days=1)


@pytest.mark.parametrize(
    ("last_modified", "expect"),
    [
        (modified, 206),
        (before, 200),
        (after, 200),
        (None, 200),
    ],
)
def test_if_range_date(last_modified: dt.datetime | None, expect: int) -> None:
    response = make_response(
        range=five, if_range=IfRange(date=modified), last_modified=last_modified
    )
    assert response.status_code == expect
