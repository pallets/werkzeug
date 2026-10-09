from __future__ import annotations

import pytest

from werkzeug.sansio.utils import get_host
from werkzeug.sansio.utils import host_is_trusted


@pytest.mark.parametrize(
    ("scheme", "host_header", "server", "expected"),
    [
        ("http", "spam", None, "spam"),
        ("http", "spam:80", None, "spam"),
        ("https", "spam", None, "spam"),
        ("https", "spam:443", None, "spam"),
        ("http", "spam:8080", None, "spam:8080"),
        ("http", "127.0.0.1:8080", None, "127.0.0.1:8080"),
        ("http", "[::1]:8080", None, "[::1]:8080"),
        ("ws", "spam", None, "spam"),
        ("ws", "spam:80", None, "spam"),
        ("wss", "spam", None, "spam"),
        ("wss", "spam:443", None, "spam"),
        ("http", None, ("spam", 80), "spam"),
        ("http", None, ("spam", 8080), "spam:8080"),
        ("http", None, ("127.0.0.1", 8080), "127.0.0.1:8080"),
        ("http", None, ("::1", 8080), "[::1]:8080"),
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


def test_get_host_unix() -> None:
    assert get_host("http", None, ("unix/socket", None)) == ""


def test_get_host_missing() -> None:
    assert get_host("http", None, None) == ""


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a.test:8080@b.test",
        "a.test:port",
        "[z:443]:8080",
        "a.test:0",
        "a.test:65536",
        "a.test:0443",
        "a.test:",
    ],
)
def test_get_host_invalid(value: str | None) -> None:
    assert get_host("http", value, None) == ""


@pytest.mark.parametrize(
    ("host", "trust", "expect"),
    [
        ("a.test", ["a.test"], True),
        ("b.a.test", ["a.test"], False),
        ("a.test", [".a.test"], True),
        ("b.a.test", [".a.test"], True),
        ("a.test", ["a.example"], False),
        ("a.test:8080", ["a.test"], True),
        ("a.test:8080", ["a.example"], False),
        ("", ["a.test"], False),
        ("a.test", [], True),
    ],
)
def test_trusted(host: str, trust: list[str], expect: bool) -> None:
    assert host_is_trusted(host, trust) is expect
