import typing as t

import pytest

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
    host_header: t.Optional[str],
    server: t.Optional[t.Tuple[str, t.Optional[int]]],
    expected: str,
) -> None:
    assert get_host(scheme, host_header, server) == expected
