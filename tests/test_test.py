# -*- coding: utf-8 -*-
"""
    werkzeug.test test
    ~~~~~~~~~~~~~~~~~~

    "Quis custodiet ipsos custodes?"

       -- "Who will police the police?", or in this case:

    Who will test the test?

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

from werkzeug.wrappers import Request, Response
from werkzeug.test import Client


def cookie_app(environ, start_response):
    """A WSGI application which sets a cookie, and returns as a ersponse any
    cookie which exists.
    """
    response = Response(environ.get('HTTP_COOKIE', 'No Cookie'),
                        mimetype='text/plain')
    response.set_cookie('test', 'test')
    return response(environ, start_response)


def test_set_cookie_app():
    """Test that a server cookie is set and stored in the client
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'Set-Cookie' in dict(headers)


def test_cookiejar_stores_cookie():
    """Test that the cookie jar in the test client stores the cookie
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert 'test' in c.cookie_jar._cookies['localhost.local']['/']


def test_no_initial_cookie():
    """Test there is no cookie set in the client initially.
    """
    c = Client(cookie_app)
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_resent_cookie():
    """Test that the client resends cookies on subsequent requests,
    """
    c = Client(cookie_app)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'test=test'


def test_disable_cookies():
    """Ensure that cookies are not stored when use_cookies is False in the
    client.
    """
    c = Client(cookie_app, use_cookies=False)
    c.open()
    appiter, code, headers = c.open()
    assert ''.join(appiter) == 'No Cookie'


def test_cookie_for_different_path():
    """Test that the client resends cookies on subsequent requests for
    different paths.
    """
    c = Client(cookie_app)
    c.open('/path1')
    appiter, code, headers = c.open('/path2')
    assert ''.join(appiter) == 'test=test'

