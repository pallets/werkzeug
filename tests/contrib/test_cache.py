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
    _can_use_fast_sleep = True

    @pytest.fixture
    def make_cache(self):
        '''Return a cache class or factory.'''
        raise NotImplementedError()

    @pytest.fixture
    def fast_sleep(self, monkeypatch):
        if self._can_use_fast_sleep:
            def sleep(delta):
                orig_time = cache.time
                monkeypatch.setattr(cache, 'time', lambda: orig_time() + delta)

            return sleep
        else:
            import time
            return time.sleep

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
        assert list(c.get_many('foo', 'spam')) == [['bar'], 'eggs']

    def test_generic_set_many(self, c):
        assert c.set_many({'foo': 'bar', 'spam': ['eggs']})
        assert c.get('foo') == 'bar'
        assert c.get('spam') == ['eggs']

    def test_generic_expire(self, c, fast_sleep):
        assert c.set('foo', 'bar', 1)
        fast_sleep(2)
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

    def test_purge(self):
        c = cache.SimpleCache(threshold=2)
        c.set('a', 'a')
        c.set('b', 'b')
        c.set('c', 'c')
        c.set('d', 'd')
        # Cache purges old items *before* it sets new ones.
        assert len(c._cache) == 3


class TestSimpleCache(CacheTests):
    @pytest.fixture
    def make_cache(self):
        return cache.SimpleCache


class TestFileSystemCache(CacheTests):
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


# Don't use pytest marker
# https://bitbucket.org/hpk42/pytest/issue/568
if redis is not None:
    class TestRedisCache(CacheTests):
        _can_use_fast_sleep = False

        @pytest.fixture(params=[
            ([], dict()),
            ([redis.Redis()], dict()),
            ([redis.StrictRedis()], dict())
        ])
        def make_cache(self, xprocess, request):
            def preparefunc(cwd):
                return 'server is now ready', ['redis-server']

            xprocess.ensure('redis_server', preparefunc)
            args, kwargs = request.param
            c = cache.RedisCache(*args, key_prefix='werkzeug-test-case:',
                                 **kwargs)
            request.addfinalizer(c.clear)
            return lambda: c

        def test_compat(self, c):
            assert c._client.set(c.key_prefix + 'foo', 'Awesome')
            assert c.get('foo') == b'Awesome'
            assert c._client.set(c.key_prefix + 'foo', '42')
            assert c.get('foo') == 42


# Don't use pytest marker
# https://bitbucket.org/hpk42/pytest/issue/568
if memcache is not None:
    class TestMemcachedCache(CacheTests):
        _can_use_fast_sleep = False

        @pytest.fixture
        def make_cache(self, xprocess, request):
            def preparefunc(cwd):
                return '', ['memcached']

            xprocess.ensure('memcached', preparefunc)
            c = cache.MemcachedCache(key_prefix='werkzeug-test-case:')
            request.addfinalizer(c.clear)
            return lambda: c

        def test_compat(self, c):
            assert c._client.set(c.key_prefix + 'foo', 'bar')
            assert c.get('foo') == 'bar'

        def test_huge_timeouts(self, c):
            # Timeouts greater than epoch are interpreted as POSIX timestamps
            # (i.e. not relative to now, but relative to epoch)
            import random
            epoch = 2592000
            timeout = epoch + random.random() * 100
            c.set('foo', 'bar', timeout)
            assert c.get('foo') == 'bar'
