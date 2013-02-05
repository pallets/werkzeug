# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.sessions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Added tests for the sessions.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import unittest
import shutil

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug.contrib.cache import SimpleCache
from werkzeug.contrib.sessions import FilesystemSessionStore, CacheSessionStore

from tempfile import mkdtemp, gettempdir


class SessionTestCase(WerkzeugTestCase):

    def create_session(self, **kwargs):
        raise NotImplementedError

    def test_basic_sessions(self):
        store = self.create_session()
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
        self.assert_equal(x, x2)
        x2['test'] = 3
        assert x2.modified
        assert not x2.new
        store.save(x2)

        x = store.get(x.sid)
        store.delete(x)
        x2 = store.get(x.sid)
        # the session is not new when it was used previously.
        assert not x2.new

    def test_renewing_session(self):
        store = self.create_session(renew_missing=True)
        x = store.new()
        store.save(x)
        store.delete(x)
        x2 = store.get(x.sid)
        assert x2.new


class FilesystemSessionTestCase(SessionTestCase):

    def setup(self):
        self.session_folder = mkdtemp()

    def teardown(self):
        shutil.rmtree(self.session_folder)

    def create_session(self, **kwargs):
        return FilesystemSessionStore(self.session_folder, **kwargs)

    def test_default_tempdir(self):
        store = FilesystemSessionStore()
        assert store.path == gettempdir()

    def test_session_lising(self):
        store = self.create_session(renew_missing=True)
        sessions = set()
        for x in xrange(10):
            sess = store.new()
            store.save(sess)
            sessions.add(sess.sid)

        listed_sessions = set(store.list())
        assert sessions == listed_sessions


class CacheSessionTestCase(SessionTestCase):

    def create_session(self, **kwargs):
        return CacheSessionStore(SimpleCache(), 'cache_', **kwargs)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FilesystemSessionTestCase))
    suite.addTest(unittest.makeSuite(CacheSessionTestCase))
    return suite
