# -*- coding: utf-8 -*-
"""
    tests.cache
    ~~~~~~~~~~~

    Tests the cache system

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest
import os
import time
import tempfile
import shutil

from tests import WerkzeugTests
from werkzeug.contrib import cache

try:
    import redis
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

class CacheTests(object):
    @pytest.fixture
    def make_cache(self):
        '''Return a cache class or factory.'''
        raise NotImplementedError()

    @pytest.fixture
    def c(self, make_cache):
        '''Return a cache instance.'''
        return make_cache()

    def test_generic_get_dict(self, c):
        assert c.set('a', 'a')
        assert c.set('b', 'b')
        d = c.get_dict('a', 'b')
        assert 'a' in d
        assert 'a' == d['a']
        assert 'b' in d
        assert 'b' == d['b']

    def test_generic_set_many(self, c):
        assert c.set_many({0: 0, 1: 1, 2: 4})
        assert c.get(2) == 4
        assert c.set_many((i, i*i) for i in range(3))
        assert c.get(2) == 4

    def test_generic_set_get(self, c):
        for i in range(3):
            assert c.set(str(i), i * i)
        for i in range(3):
            result = c.get(str(i))
            assert result == i * i, result

    def test_generic_get_set(self, c):
        assert c.set('foo', ['bar'])
        assert c.get('foo') == ['bar']

    def test_generic_get_many(self, c):
        assert c.set('foo', ['bar'])
        assert c.set('spam', 'eggs')
        self.assert_equal(list(c.get_many('foo', 'spam')), [['bar'], 'eggs'])

    def test_generic_set_many(self, c):
        assert c.set_many({'foo': 'bar', 'spam': ['eggs']})
        assert c.get('foo') == 'bar'
        assert c.get('spam') == ['eggs']

    def test_generic_expire(self, c):
        assert c.set('foo', 'bar', 1)
        time.sleep(2)
        assert c.get('foo') is None

    def test_generic_add(self, c):
        # sanity check that add() works like set()
        assert c.add('foo', 'bar')
        assert c.get('foo') == 'bar'
        assert not c.add('foo', 'qux')
        assert c.get('foo') == 'bar'

    def test_generic_delete(self, c):
        assert c.add('foo', 'bar')
        assert c.get('foo') == 'bar'
        assert c.delete('foo')
        assert c.get('foo') is None

    def test_generic_delete_many(self, c):
        assert c.add('foo', 'bar')
        assert c.add('spam', 'eggs')
        assert c.delete_many('foo', 'spam')
        assert c.get('foo') is None
        assert c.get('spam') is None

    def test_generic_inc_dec(self, c):
        assert c.set('foo', 1)
        assert c.inc('foo') == c.get('foo') == 2
        assert c.dec('foo') == c.get('foo') == 1
        assert c.delete('foo')

    def test_generic_true_false(self, c):
        assert c.set('foo', True)
        assert c.get('foo') == True
        assert c.set('bar', False)
        assert c.get('bar') == False


class TestSimpleCache(WerkzeugTests, CacheTests):
    @pytest.fixture
    def make_cache(self):
        return cache.SimpleCache


class TestFileSystemCache(WerkzeugTests, CacheTests):
    @pytest.fixture
    def make_cache(self, tmpdir):
        return lambda **kw: cache.FileSystemCache(cache_dir=str(tmpdir), **kw)

    def test_filesystemcache_prune(self, make_cache):
        THRESHOLD = 13
        c = make_cache(threshold=THRESHOLD)
        for i in range(2 * THRESHOLD):
            assert c.set(str(i), i)
        cache_files = os.listdir(c._path)
        assert len(cache_files) <= THRESHOLD

    def test_filesystemcache_clear(self, c):
        assert c.set('foo', 'bar')
        cache_files = os.listdir(c._path)
        assert len(cache_files) == 1
        assert c.clear()
        cache_files = os.listdir(c._path)
        assert len(cache_files) == 0


@pytest.mark.skipif(redis is None, reason='Redis is not installed.')
class TestRedisCache(WerkzeugTests, CacheTests):

    @pytest.fixture
    def make_cache(self, request):
        c = cache.RedisCache(key_prefix='werkzeug-test-case:')
        request.addfinalizer(c.clear)
        return lambda: c

    def test_compat(self, c):
        assert c._client.set(c.key_prefix + 'foo', 'Awesome')
        assert c.get('foo') == b'Awesome'
        assert c._client.set(c.key_prefix + 'foo', '42')
        assert c.get('foo') == 42


@pytest.mark.skipif(memcache is None, reason='Memcache is not installed.')
class TestMemcachedCache(WerkzeugTests, CacheTests):

    @pytest.fixture
    def make_cache(self, request):
        c = cache.MemcachedCache(key_prefix='werkzeug-test-case:')
        request.addfinalizer(c.clear)
        return lambda: c

    def test_compat(self, c):
        assert c._client.set(c.key_prefix + b'foo', 'bar')
        assert c.get('foo') == 'bar'
