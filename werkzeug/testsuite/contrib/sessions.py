# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.sessions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Added tests for the sessions.

    :copyright: (c) 2013 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import unittest
import shutil
from tempfile import mkdtemp, gettempdir

from werkzeug.testsuite import WerkzeugTestCase
from werkzeug.contrib.sessions import FilesystemSessionStore, SessionMiddleware

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse


class SessionTestCase(WerkzeugTestCase):

    def setup(self):
        self.session_folder = mkdtemp()

    def teardown(self):
        shutil.rmtree(self.session_folder)

    def test_default_tempdir(self):
        store = FilesystemSessionStore()
        assert store.path == gettempdir()

    def test_basic_fs_sessions(self):
        store = FilesystemSessionStore(self.session_folder)
        x = store.new()
        assert x.new
        assert not x.modified
        x['foo'] = [1, 2, 3]
        assert x.modified
        store.save(x)

        x2 = store.get(x.sid)
        assert not x2.new
        assert not x2.modified
        assert x2 is not x
        assert x2 == x
        x2['test'] = 3
        assert x2.modified
        assert not x2.new
        store.save(x2)

        x = store.get(x.sid)
        store.delete(x)
        x2 = store.get(x.sid)
        # the session is not new when it was used previously.
        assert not x2.new

    def test_renewing_fs_session(self):
        store = FilesystemSessionStore(self.session_folder, renew_missing=True)
        x = store.new()
        store.save(x)
        store.delete(x)
        x2 = store.get(x.sid)
        assert x2.new

    def test_fs_session_lising(self):
        store = FilesystemSessionStore(self.session_folder, renew_missing=True)
        sessions = set()
        for x in range(10):
            sess = store.new()
            store.save(sess)
            sessions.add(sess.sid)

        listed_sessions = set(store.list())
        assert sessions == listed_sessions

    def test_sessionmiddleware_setcookie(self):
        def application(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/html')])
            session = environ['werkzeug.session']
            if session.new:
                session['visit_count'] = 0
            yield '%s' % session['visit_count']
            session['visit_count'] += 1

        store = FilesystemSessionStore(self.session_folder)
        app = SessionMiddleware(application, store)
        c = Client(app, BaseResponse)
        resp = c.get('/')
        self.assertIn('Set-Cookie', resp.headers)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SessionTestCase))
    return suite
