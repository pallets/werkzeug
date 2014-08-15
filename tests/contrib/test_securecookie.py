# -*- coding: utf-8 -*-
"""
    tests.securecookie
    ~~~~~~~~~~~~~~~~~~

    Tests the secure cookie.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

from werkzeug.utils import parse_cookie
from werkzeug.wrappers import Request, Response
from werkzeug.contrib.securecookie import SecureCookie


def test_basic_support():
    c = SecureCookie(secret_key=b'foo')
    assert c.new
    assert not c.modified
    assert not c.should_save
    c['x'] = 42
    assert c.modified
    assert c.should_save
    s = c.serialize()

    c2 = SecureCookie.unserialize(s, b'foo')
    assert c is not c2
    assert not c2.new
    assert not c2.modified
    assert not c2.should_save
    assert c2 == c

    c3 = SecureCookie.unserialize(s, b'wrong foo')
    assert not c3.modified
    assert not c3.new
    assert c3 == {}

def test_wrapper_support():
    req = Request.from_values()
    resp = Response()
    c = SecureCookie.load_cookie(req, secret_key=b'foo')
    assert c.new
    c['foo'] = 42
    assert c.secret_key == b'foo'
    c.save_cookie(resp)

    req = Request.from_values(headers={
        'Cookie':  'session="%s"' % parse_cookie(resp.headers['set-cookie'])['session']
    })
    c2 = SecureCookie.load_cookie(req, secret_key=b'foo')
    assert not c2.new
    assert c2 == c
