import os
import sys

import pytest

from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.security import safe_join


def test_default_password_method():
    value = generate_password_hash("secret")
    assert value.startswith("scrypt:")


@pytest.mark.xfail(
    sys.implementation.name == "pypy", reason="scrypt unavailable on pypy"
)
def test_scrypt():
    value = generate_password_hash("secret", method="scrypt")
    assert check_password_hash(value, "secret")
    assert value.startswith("scrypt:32768:8:1$")


def test_pbkdf2():
    value = generate_password_hash("secret", method="pbkdf2")
    assert check_password_hash(value, "secret")
    assert value.startswith("pbkdf2:sha256:1000000$")


def test_salted_hashes():
    hash1 = generate_password_hash("secret")
    hash2 = generate_password_hash("secret")
    assert hash1 != hash2
    assert check_password_hash(hash1, "secret")
    assert check_password_hash(hash2, "secret")


def test_require_salt():
    with pytest.raises(ValueError):
        generate_password_hash("secret", salt_length=0)


def test_invalid_method():
    with pytest.raises(ValueError, match="Invalid hash method"):
        generate_password_hash("secret", "sha256")


@pytest.mark.parametrize(
    ("path", "expect"),
    [
        ("b/c", "a/b/c"),
        ("../b/c", None),
        ("b\\c", None if os.name == "nt" else "a/b\\c"),
        ("//b/c", None),
    ],
)
def test_safe_join(path, expect):
    assert safe_join("a", path) == expect


def test_safe_join_os_sep():
    import werkzeug.security as sec

    prev_value = sec._os_alt_seps
    sec._os_alt_seps = "*"
    assert safe_join("foo", "bar/baz*") is None
    sec._os_alt_steps = prev_value


def test_safe_join_empty_trusted():
    assert safe_join("", "c:test.txt") == "./c:test.txt"


@pytest.mark.parametrize(
    "name", ["CON", "CON.txt", "CON.txt.html", "CON  ", "CON . txt"]
)
def test_safe_join_windows_special(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Windows special device name is not allowed on Windows."""
    monkeypatch.setattr("os.name", "nt")
    assert safe_join("a", name) is None


def test_safe_join_not_windows_special(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.name", "posix")
    assert safe_join("a", "CON") == "a/CON"
