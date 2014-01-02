# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.cache
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Tests the cache system

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import time
import unittest
import tempfile
import shutil

from werkzeug.testsuite import WerkzeugTestCase
from werkzeug.contrib import cache

try:
    import redis
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError
        cache.RedisCache(key_prefix='werkzeug-test-case:')._client.set('test','connection')
    except RedisConnectionError:
        redis = None
except ImportError:
    redis = None
try:
    import pylibmc as memcache
except ImportError:
    try:
        from google.appengine.api import memcache
    except ImportError:
        try:
            import memcache
        except ImportError:
            memcache = None

class CacheTestCase(WerkzeugTestCase):
    make_cache = None

    def test_generic_get_dict(self):
        c = self.make_cache()
        assert c.set('a', 'a')
        assert c.set('b', 'b')
        d = c.get_dict('a', 'b')
        assert 'a' in d
        assert 'a' == d['a']
        assert 'b' in d
        assert 'b' == d['b']

    def test_generic_set_many(self):
        c = self.make_cache()
        assert c.set_many({0: 0, 1: 1, 2: 4})
        assert c.get(2) == 4
        assert c.set_many((i, i*i) for i in range(3))
        assert c.get(2) == 4

    def test_generic_set_get(self):
        c = self.make_cache()
        for i in range(3):
            assert c.set(str(i), i * i)
        for i in range(3):
            result = c.get(str(i))
            assert result == i * i, result

    def test_generic_get_set(self):
        c = self.make_cache()
        assert c.set('foo', ['bar'])
        assert c.get('foo') == ['bar']

    def test_generic_get_many(self):
        c = self.make_cache()
        assert c.set('foo', ['bar'])
        assert c.set('spam', 'eggs')
        self.assert_equal(list(c.get_many('foo', 'spam')), [['bar'], 'eggs'])

    def test_generic_set_many(self):
        c = self.make_cache()
        assert c.set_many({'foo': 'bar', 'spam': ['eggs']})
        assert c.get('foo') == 'bar'
        assert c.get('spam') == ['eggs']

    def test_generic_expire(self):
        c = self.make_cache()
        assert c.set('foo', 'bar', 1)
        time.sleep(2)
        assert c.get('foo') is None

    def test_generic_add(self):
        c = self.make_cache()
        # sanity check that add() works like set()
        assert c.add('foo', 'bar')
        assert c.get('foo') == 'bar'
        assert not c.add('foo', 'qux')
        assert c.get('foo') == 'bar'

    def test_generic_delete(self):
        c = self.make_cache()
        assert c.add('foo', 'bar')
        assert c.get('foo') == 'bar'
        assert c.delete('foo')
        assert c.get('foo') is None

    def test_generic_delete_many(self):
        c = self.make_cache()
        assert c.add('foo', 'bar')
        assert c.add('spam', 'eggs')
        assert c.delete_many('foo', 'spam')
        assert c.get('foo') is None
        assert c.get('spam') is None

    def test_generic_inc_dec(self):
        c = self.make_cache()
        assert c.set('foo', 1)
        assert c.inc('foo') == c.get('foo') == 2
        assert c.dec('foo') == c.get('foo') == 1
        assert c.delete('foo')

    def test_generic_true_false(self):
        c = self.make_cache()
        assert c.set('foo', True)
        assert c.get('foo') == True
        assert c.set('bar', False)
        assert c.get('bar') == False


class SimpleCacheTestCase(CacheTestCase):
    make_cache = cache.SimpleCache


class FileSystemCacheTestCase(CacheTestCase):
    tmp_dir = None

    def make_cache(self, **kwargs):
        if self.tmp_dir is None:
            self.tmp_dir = tempfile.mkdtemp()
        return cache.FileSystemCache(cache_dir=self.tmp_dir, **kwargs)

    def teardown(self):
        if self.tmp_dir is not None:
            shutil.rmtree(self.tmp_dir)
    
    def test_filesystemcache_prune(self):
        THRESHOLD = 13
        c = self.make_cache(threshold=THRESHOLD)
        for i in range(2 * THRESHOLD):
            assert c.set(str(i), i)
        cache_files = os.listdir(self.tmp_dir)
        assert len(cache_files) <= THRESHOLD

    def test_filesystemcache_clear(self):
        c = self.make_cache()
        assert c.set('foo', 'bar')
        cache_files = os.listdir(self.tmp_dir)
        assert len(cache_files) == 1
        assert c.clear()
        cache_files = os.listdir(self.tmp_dir)
        assert len(cache_files) == 0


class RedisCacheTestCase(CacheTestCase):
    def make_cache(self):
        return cache.RedisCache(key_prefix='werkzeug-test-case:')

    def teardown(self):
        self.make_cache().clear()

    def test_compat(self):
        c = self.make_cache()
        assert c._client.set(c.key_prefix + 'foo', 'Awesome')
        self.assert_equal(c.get('foo'), b'Awesome')
        assert c._client.set(c.key_prefix + 'foo', '42')
        self.assert_equal(c.get('foo'), 42)
    

class MemcachedCacheTestCase(CacheTestCase):
    def make_cache(self):
        return cache.MemcachedCache(key_prefix='werkzeug-test-case:')

    def teardown(self):
        self.make_cache().clear()

    def test_compat(self):
        c = self.make_cache()
        assert c._client.set(c.key_prefix + b'foo', 'bar')
        self.assert_equal(c.get('foo'), 'bar')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SimpleCacheTestCase))
    suite.addTest(unittest.makeSuite(FileSystemCacheTestCase))
    if redis is not None:
        suite.addTest(unittest.makeSuite(RedisCacheTestCase))
    if memcache is not None:
        suite.addTest(unittest.makeSuite(MemcachedCacheTestCase))
    return suite
