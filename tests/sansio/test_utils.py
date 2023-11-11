from __future__ import annotations

import pytest

from werkzeug.sansio.utils import get_content_length
from werkzeug.sansio.utils import get_host


@pytest.mark.parametrize(
    ("scheme", "host_header", "server", "expected"),
    [
        ("http", "spam", None, "spam"),
        ("http", "spam:80", None, "spam"),
        ("https", "spam", None, "spam"),
        ("https", "spam:443", None, "spam"),
        ("http", "spam:8080", None, "spam:8080"),
        ("ws", "spam", None, "spam"),
        ("ws", "spam:80", None, "spam"),
        ("wss", "spam", None, "spam"),
        ("wss", "spam:443", None, "spam"),
        ("http", None, ("spam", 80), "spam"),
        ("http", None, ("spam", 8080), "spam:8080"),
        ("http", None, ("unix/socket", None), "unix/socket"),
        ("http", "spam", ("eggs", 80), "spam"),
    ],
)
def test_get_host(
    scheme: str,
    host_header: str | None,
    server: tuple[str, int | None] | None,
    expected: str,
) -> None:
    assert get_host(scheme, host_header, server) == expected


@pytest.mark.parametrize(
    ("http_content_length", "http_transfer_encoding", "expected"),
    [
        ("2", None, 2),
        (" 2", None, 2),
        ("2 ", None, 2),
        (None, None, None),
        (None, "chunked", None),
        ("a", None, 0),
        ("-2", None, 0),
    ],
)
def test_get_content_length(
    http_content_length: str | None,
    http_transfer_encoding: str | None,
    expected: int | None,
) -> None:
    assert get_content_length(http_content_length, http_transfer_encoding) == expected
