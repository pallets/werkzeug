# -*- coding: utf-8 -*-
"""
    werkzeug.serving test
    ~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import time
import urllib
from werkzeug import serving, test_app, __version__ as version
from threading import Thread


real_make_server = serving.make_server


def run_dev_server(application):
    servers = []
    def tracking_make_server(*args, **kwargs):
        srv = real_make_server(*args, **kwargs)
        servers.append(srv)
        return srv
    serving.make_server = tracking_make_server
    try:
        t = Thread(target=serving.run_simple, args=('localhost', 0, application))
        t.setDaemon(True)
        t.start()
        time.sleep(0.25)
    finally:
        serving.make_server = real_make_server
    if not servers:
        return None, None
    server ,= servers
    ip, port = server.socket.getsockname()[:2]
    if ':' in ip:
        ip = '[%s]' % ip
    return server, '%s:%d'  % (ip, port)


def test_serving():
    """Test server"""
    server, addr = run_dev_server(test_app)
    rv = urllib.urlopen('http://%s/?foo=bar&baz=blah' % addr).read()
    assert 'WSGI Information' in rv
    assert 'foo=bar&amp;baz=blah' in rv
    assert ('Werkzeug/%s' % version) in rv


def test_broken_app():
    """Broken apps in server"""
    def broken_app(environ, start_response):
        1/0
    server, addr = run_dev_server(broken_app)
    rv = urllib.urlopen('http://%s/?foo=bar&baz=blah' % addr).read()
    assert 'Internal Server Error' in rv
