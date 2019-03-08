# -*- coding: utf-8 -*-
"""
    tests.securecookie
    ~~~~~~~~~~~~~~~~~~

    Tests the secure cookie.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import json

import pytest

from werkzeug._compat import to_native
from werkzeug.contrib.securecookie import SecureCookie
from werkzeug.utils import parse_cookie
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


def test_basic_support():
    c = SecureCookie(secret_key=b"foo")
    assert c.new
    assert not c.modified
    assert not c.should_save
    c["x"] = 42
    assert c.modified
    assert c.should_save
    s = c.serialize()

    c2 = SecureCookie.unserialize(s, b"foo")
    assert c is not c2
    assert not c2.new
    assert not c2.modified
    assert not c2.should_save
    assert c2 == c

    c3 = SecureCookie.unserialize(s, b"wrong foo")
    assert not c3.modified
    assert not c3.new
    assert c3 == {}

    c4 = SecureCookie({"x": 42}, "foo")
    c4_serialized = c4.serialize()
    assert SecureCookie.unserialize(c4_serialized, "foo") == c4


def test_wrapper_support():
    req = Request.from_values()
    resp = Response()
    c = SecureCookie.load_cookie(req, secret_key=b"foo")
    assert c.new
    c["foo"] = 42
    assert c.secret_key == b"foo"
    c.save_cookie(resp)

    req = Request.from_values(
        headers={
            "Cookie": 'session="%s"'
            % parse_cookie(resp.headers["set-cookie"])["session"]
        }
    )
    c2 = SecureCookie.load_cookie(req, secret_key=b"foo")
    assert not c2.new
    assert c2 == c


def test_pickle_deprecated():
    with pytest.warns(UserWarning):
        SecureCookie({"foo": "bar"}, "secret").serialize()


def test_json():
    class JSONCompat(object):
        dumps = staticmethod(json.dumps)

        @staticmethod
        def loads(s):
            # json on Python < 3.6 fails on bytes
            return json.loads(to_native(s, "utf8"))

    class JSONSecureCookie(SecureCookie):
        serialization_method = JSONCompat

    secure = JSONSecureCookie({"foo": "bar"}, "secret").serialize()
    data = JSONSecureCookie.unserialize(secure, "secret")
    assert data == {"foo": "bar"}
