from __future__ import annotations

import datetime as dt

import pytest

from werkzeug.datastructures.etag import ETag
from werkzeug.datastructures.etag import ETagSet
from werkzeug.datastructures.headers import Headers
from werkzeug.exceptions import PreconditionFailed
from werkzeug.http import http_date
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers.response import Response


def make_response(
    *,
    method: str = "GET",
    if_match: ETagSet | None = None,
    if_unmodified_since: dt.datetime | None = None,
    if_none_match: ETagSet | None = None,
    if_modified_since: dt.datetime | None = None,
    etag: ETag | None = None,
    last_modified: dt.datetime | None = None,
    exists: bool = True,
) -> Response:
    headers = Headers()

    if if_match is not None:
        headers["If-Match"] = if_match.to_header()

    if if_unmodified_since is not None:
        headers["If-Unmodified-Since"] = http_date(if_unmodified_since)

    if if_none_match is not None:
        headers["If-None-Match"] = if_none_match.to_header()

    if if_modified_since is not None:
        headers["If-Modified-Since"] = http_date(if_modified_since)

    request = EnvironBuilder(method=method, headers=headers).get_request()
    response = Response("Hello, World!")
    response.etag = etag
    response.last_modified = last_modified
    response.apply_conditions(request, exists=exists)
    return response


def test_if_match() -> None:
    assert make_response(if_match=ETagSet(["a"]), etag=ETag("a")).status_code == 200


@pytest.mark.parametrize(
    ("value", "etag"),
    [
        (ETagSet(["b"]), ETag("a")),
        (ETagSet(["a"]), ETag("a", weak=True)),
        (ETagSet([], ["a"]), ETag("a")),
        (ETagSet(["a"]), None),
    ],
)
def test_if_match_fail(value: ETagSet, etag: ETag | None) -> None:
    with pytest.raises(PreconditionFailed):
        make_response(if_match=value, etag=etag)


def test_if_match_star_exists() -> None:
    response = make_response(if_match=ETagSet(star_tag=True), exists=True)
    assert response.status_code == 200


def test_if_match_star_fail() -> None:
    with pytest.raises(PreconditionFailed):
        make_response(if_match=ETagSet(star_tag=True), exists=False)


modified = dt.datetime(2026, 9, 26, 8, 15, tzinfo=dt.UTC)
before = modified - dt.timedelta(days=1)
after = modified + dt.timedelta(days=1)


@pytest.mark.parametrize(
    ("value", "last_modified"),
    [(modified, modified), (after, modified), (modified, None)],
)
def test_if_unmodified_since(
    value: dt.datetime, last_modified: dt.datetime | None
) -> None:
    response = make_response(if_unmodified_since=value, last_modified=last_modified)
    assert response.status_code == 200


def test_if_unmodified_since_fail() -> None:
    with pytest.raises(PreconditionFailed):
        make_response(if_unmodified_since=before, last_modified=modified)


def test_if_match_precedence() -> None:
    response = make_response(
        if_match=ETagSet(["a"]),
        etag=ETag("a"),
        if_unmodified_since=before,
        last_modified=modified,
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("value", "etag", "expect"),
    [
        (ETagSet(["a"]), ETag("a"), 304),
        (ETagSet([], ["a"]), ETag("a"), 304),
        (ETagSet(["a"]), ETag("a", weak=True), 304),
        (ETagSet(["b"]), ETag("a"), 200),
        (ETagSet(["a"]), None, 200),
    ],
)
def test_if_none_match(value: ETagSet, etag: ETag | None, expect: int) -> None:
    response = make_response(if_none_match=value, etag=etag)
    assert response.status_code == expect


def test_if_none_match_post() -> None:
    with pytest.raises(PreconditionFailed):
        make_response(method="POST", if_none_match=ETagSet(["a"]), etag=ETag("a"))


@pytest.mark.parametrize(("exists", "expect"), [(True, 304), (False, 200)])
def test_if_none_match_star(exists: bool, expect: int) -> None:
    response = make_response(if_none_match=ETagSet(star_tag=True), exists=exists)
    assert response.status_code == expect


@pytest.mark.parametrize(
    ("value", "last_modified", "expect"),
    [
        (modified, modified, 304),
        (after, modified, 304),
        (before, modified, 200),
        (modified, None, 200),
    ],
)
def test_if_modified_since(
    value: dt.datetime, last_modified: dt.datetime | None, expect: int
) -> None:
    response = make_response(if_modified_since=value, last_modified=last_modified)
    assert response.status_code == expect


def test_if_modified_since_post() -> None:
    response = make_response(
        method="POST", if_modified_since=after, last_modified=modified
    )
    assert response.status_code == 200


def test_if_none_match_precedence() -> None:
    response = make_response(
        if_none_match=ETagSet(["b"]),
        etag=ETag("a"),
        if_modified_since=modified,
        last_modified=modified,
    )
    assert response.status_code == 200
