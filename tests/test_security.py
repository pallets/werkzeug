# -*- coding: utf-8 -*-
"""
    tests.security
    ~~~~~~~~~~~~~~

    Tests the security helpers.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import os
import posixpath

import pytest

from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.security import pbkdf2_hex
from werkzeug.security import safe_join
from werkzeug.security import safe_str_cmp


def test_safe_str_cmp():
    assert safe_str_cmp("a", "a") is True
    assert safe_str_cmp(b"a", u"a") is True
    assert safe_str_cmp("a", "b") is False
    assert safe_str_cmp(b"aaa", "aa") is False
    assert safe_str_cmp(b"aaa", "bbb") is False
    assert safe_str_cmp(b"aaa", u"aaa") is True
    assert safe_str_cmp(u"aaa", u"aaa") is True


def test_safe_str_cmp_no_builtin():
    import werkzeug.security as sec

    prev_value = sec._builtin_safe_str_cmp
    sec._builtin_safe_str_cmp = None
    assert safe_str_cmp("a", "ab") is False

    assert safe_str_cmp("str", "str") is True
    assert safe_str_cmp("str1", "str2") is False
    sec._builtin_safe_str_cmp = prev_value


def test_password_hashing():
    hash0 = generate_password_hash("default")
    assert check_password_hash(hash0, "default")
    assert hash0.startswith("pbkdf2:sha256:150000$")

    hash1 = generate_password_hash("default", "sha1")
    hash2 = generate_password_hash(u"default", method="sha1")
    assert hash1 != hash2
    assert check_password_hash(hash1, "default")
    assert check_password_hash(hash2, "default")
    assert hash1.startswith("sha1$")
    assert hash2.startswith("sha1$")

    with pytest.raises(ValueError):
        check_password_hash("$made$up$", "default")

    with pytest.raises(ValueError):
        generate_password_hash("default", "sha1", salt_length=0)

    fakehash = generate_password_hash("default", method="plain")
    assert fakehash == "plain$$default"
    assert check_password_hash(fakehash, "default")

    mhash = generate_password_hash(u"default", method="md5")
    assert mhash.startswith("md5$")
    assert check_password_hash(mhash, "default")

    legacy = "md5$$c21f969b5f03d33d43e04f8f136e7682"
    assert check_password_hash(legacy, "default")

    legacy = u"md5$$c21f969b5f03d33d43e04f8f136e7682"
    assert check_password_hash(legacy, "default")


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


def test_pbkdf2():
    def check(data, salt, iterations, keylen, hashfunc, expected):
        rv = pbkdf2_hex(data, salt, iterations, keylen, hashfunc)
        assert rv == expected

    # From RFC 6070

    # Assumes default keylen is 20
    # check('password', 'salt', 1, None,
    #      '0c60c80f961f0e71f3a9b524af6012062fe037a6')
    check("password", "salt", 1, 20, "sha1", "0c60c80f961f0e71f3a9b524af6012062fe037a6")
    check("password", "salt", 2, 20, "sha1", "ea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957")
    check(
        "password", "salt", 4096, 20, "sha1", "4b007901b765489abead49d926f721d065a429c1"
    )
    check(
        "passwordPASSWORDpassword",
        "saltSALTsaltSALTsaltSALTsaltSALTsalt",
        4096,
        25,
        "sha1",
        "3d2eec4fe41c849b80c8d83662c0e44a8b291a964cf2f07038",
    )
    check(
        "pass\x00word", "sa\x00lt", 4096, 16, "sha1", "56fa6aa75548099dcc37d7f03425e0c3"
    )

    # PBKDF2-HMAC-SHA256 test vectors
    check(
        "password",
        "salt",
        1,
        32,
        "sha256",
        "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b",
    )
    check(
        "password",
        "salt",
        2,
        32,
        "sha256",
        "ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43",
    )
    check(
        "password",
        "salt",
        4096,
        20,
        "sha256",
        "c5e478d59288c841aa530db6845c4c8d962893a0",
    )

    # This one is from the RFC but it just takes for ages
    # check('password', 'salt', 16777216, 20,
    #       'eefe3d61cd4da4e4e9945b3d6ba2158c2634e984')

    # From Crypt-PBKDF2
    check(
        "password",
        "ATHENA.MIT.EDUraeburn",
        1,
        16,
        "sha1",
        "cdedb5281bb2f801565a1122b2563515",
    )
    check(
        "password",
        "ATHENA.MIT.EDUraeburn",
        1,
        32,
        "sha1",
        "cdedb5281bb2f801565a1122b25635150ad1f7a04bb9f3a333ecc0e2e1f70837",
    )
    check(
        "password",
        "ATHENA.MIT.EDUraeburn",
        2,
        16,
        "sha1",
        "01dbee7f4a9e243e988b62c73cda935d",
    )
    check(
        "password",
        "ATHENA.MIT.EDUraeburn",
        2,
        32,
        "sha1",
        "01dbee7f4a9e243e988b62c73cda935da05378b93244ec8f48a99e61ad799d86",
    )
    check(
        "password",
        "ATHENA.MIT.EDUraeburn",
        1200,
        32,
        "sha1",
        "5c08eb61fdf71e4e4ec3cf6ba1f5512ba7e52ddbc5e5142f708a31e2e62b1e13",
    )
    check(
        "X" * 64,
        "pass phrase equals block size",
        1200,
        32,
        "sha1",
        "139c30c0966bc32ba55fdbf212530ac9c5ec59f1a452f5cc9ad940fea0598ed1",
    )
    check(
        "X" * 65,
        "pass phrase exceeds block size",
        1200,
        32,
        "sha1",
        "9ccad6d468770cd51b10e6a68721be611a8b4d282601db3b36be9246915ec82a",
    )
