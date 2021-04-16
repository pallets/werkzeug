import os
import posixpath

import pytest

from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.security import safe_join


def test_password_hashing():
    hash0 = generate_password_hash("default")
    assert check_password_hash(hash0, "default")
    assert hash0.startswith("pbkdf2:sha256:260000$")

    hash1 = generate_password_hash("default", "sha1")
    hash2 = generate_password_hash("default", method="sha1")
    assert hash1 != hash2
    assert check_password_hash(hash1, "default")
    assert check_password_hash(hash2, "default")
    assert hash1.startswith("sha1$")
    assert hash2.startswith("sha1$")

    with pytest.raises(ValueError):
        generate_password_hash("default", "sha1", salt_length=0)

    fakehash = generate_password_hash("default", method="plain")
    assert fakehash == "plain$$default"
    assert check_password_hash(fakehash, "default")


def test_safe_join():
    assert safe_join("foo", "bar/baz") == posixpath.join("foo", "bar/baz")
    assert safe_join("foo", "../bar/baz") is None
    if os.name == "nt":
        assert safe_join("foo", "foo\\bar") is None


def test_safe_join_os_sep():
    import werkzeug.security as sec

    prev_value = sec._os_alt_seps
    sec._os_alt_seps = "*"
    assert safe_join("foo", "bar/baz*") is None
    sec._os_alt_steps = prev_value
