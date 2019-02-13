# -*- coding: utf-8 -*-
"""
    tests.cache
    ~~~~~~~~~~~

    Tests the cache system

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import errno

import pytest

from werkzeug._compat import text_type
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

pytestmark = pytest.mark.skip("werkzeug.contrib.cache moved to cachelib")


class CacheTestsBase(object):
    _can_use_fast_sleep = True
    _guaranteed_deletes = True

    @pytest.fixture
    def fast_sleep(self, monkeypatch):
        if self._can_use_fast_sleep:

            def sleep(delta):
                orig_time = cache.time
                monkeypatch.setattr(cache, "time", lambda: orig_time() + delta)

            return sleep
        else:
            import time

            return time.sleep

    @pytest.fixture
    def make_cache(self):
        """Return a cache class or factory."""
        raise NotImplementedError()

    @pytest.fixture
    def c(self, make_cache):
        """Return a cache instance."""
        return make_cache()


class GenericCacheTests(CacheTestsBase):
    def test_generic_get_dict(self, c):
        assert c.set("a", "a")
        assert c.set("b", "b")
        d = c.get_dict("a", "b")
        assert "a" in d
        assert "a" == d["a"]
        assert "b" in d
        assert "b" == d["b"]

    def test_generic_set_get(self, c):
        for i in range(3):
            assert c.set(str(i), i * i)

        for i in range(3):
            result = c.get(str(i))
            assert result == i * i, result

    def test_generic_get_set(self, c):
        assert c.set("foo", ["bar"])
        assert c.get("foo") == ["bar"]

    def test_generic_get_many(self, c):
        assert c.set("foo", ["bar"])
        assert c.set("spam", "eggs")
        assert c.get_many("foo", "spam") == [["bar"], "eggs"]

    def test_generic_set_many(self, c):
        assert c.set_many({"foo": "bar", "spam": ["eggs"]})
        assert c.get("foo") == "bar"
        assert c.get("spam") == ["eggs"]

    def test_generic_add(self, c):
        # sanity check that add() works like set()
        assert c.add("foo", "bar")
        assert c.get("foo") == "bar"
        assert not c.add("foo", "qux")
        assert c.get("foo") == "bar"

    def test_generic_delete(self, c):
        assert c.add("foo", "bar")
        assert c.get("foo") == "bar"
        assert c.delete("foo")
        assert c.get("foo") is None

    def test_generic_delete_many(self, c):
        assert c.add("foo", "bar")
        assert c.add("spam", "eggs")
        assert c.delete_many("foo", "spam")
        assert c.get("foo") is None
        assert c.get("spam") is None

    def test_generic_inc_dec(self, c):
        assert c.set("foo", 1)
        assert c.inc("foo") == c.get("foo") == 2
        assert c.dec("foo") == c.get("foo") == 1
        assert c.delete("foo")

    def test_generic_true_false(self, c):
        assert c.set("foo", True)
        assert c.get("foo") in (True, 1)
        assert c.set("bar", False)
        assert c.get("bar") in (False, 0)

    def test_generic_timeout(self, c, fast_sleep):
        c.set("foo", "bar", 0)
        assert c.get("foo") == "bar"
        c.set("baz", "qux", 1)
        assert c.get("baz") == "qux"
        fast_sleep(3)
        # timeout of zero means no timeout
        assert c.get("foo") == "bar"
        if self._guaranteed_deletes:
            assert c.get("baz") is None

    def test_generic_has(self, c):
        assert c.has("foo") in (False, 0)
        assert c.has("spam") in (False, 0)
        assert c.set("foo", "bar")
        assert c.has("foo") in (True, 1)
        assert c.has("spam") in (False, 0)
        c.delete("foo")
        assert c.has("foo") in (False, 0)
        assert c.has("spam") in (False, 0)


class TestSimpleCache(GenericCacheTests):
    @pytest.fixture
    def make_cache(self):
        return cache.SimpleCache

    def test_purge(self):
        c = cache.SimpleCache(threshold=2)
        c.set("a", "a")
        c.set("b", "b")
        c.set("c", "c")
        c.set("d", "d")
        # Cache purges old items *before* it sets new ones.
        assert len(c._cache) == 3


class TestFileSystemCache(GenericCacheTests):
    @pytest.fixture
    def make_cache(self, tmpdir):
        return lambda **kw: cache.FileSystemCache(cache_dir=str(tmpdir), **kw)

    def test_filesystemcache_prune(self, make_cache):
        THRESHOLD = 13
        c = make_cache(threshold=THRESHOLD)

        for i in range(2 * THRESHOLD):
            assert c.set(str(i), i)

        nof_cache_files = c.get(c._fs_count_file)
        assert nof_cache_files <= THRESHOLD

    def test_filesystemcache_clear(self, c):
        assert c.set("foo", "bar")
        nof_cache_files = c.get(c._fs_count_file)
        assert nof_cache_files == 1
        assert c.clear()
        nof_cache_files = c.get(c._fs_count_file)
        assert nof_cache_files == 0
        cache_files = c._list_dir()
        assert len(cache_files) == 0

    def test_no_threshold(self, make_cache):
        THRESHOLD = 0
        c = make_cache(threshold=THRESHOLD)

        for i in range(10):
            assert c.set(str(i), i)

        cache_files = c._list_dir()
        assert len(cache_files) == 10

        # File count is not maintained with threshold = 0
        nof_cache_files = c.get(c._fs_count_file)
        assert nof_cache_files is None

    def test_count_file_accuracy(self, c):
        assert c.set("foo", "bar")
        assert c.set("moo", "car")
        c.add("moo", "tar")
        assert c.get(c._fs_count_file) == 2
        assert c.add("too", "far")
        assert c.get(c._fs_count_file) == 3
        assert c.delete("moo")
        assert c.get(c._fs_count_file) == 2
        assert c.clear()
        assert c.get(c._fs_count_file) == 0


# don't use pytest.mark.skipif on subclasses
# https://bitbucket.org/hpk42/pytest/issue/568
# skip happens in requirements fixture instead
class TestRedisCache(GenericCacheTests):
    _can_use_fast_sleep = False

    @pytest.fixture(scope="class", autouse=True)
    def requirements(self, xprocess):
        if redis is None:
            pytest.skip('Python package "redis" is not installed.')

        def prepare(cwd):
            return "[Rr]eady to accept connections", ["redis-server"]

        try:
            xprocess.ensure("redis_server", prepare)
        except IOError as e:
            # xprocess raises FileNotFoundError
            if e.errno == errno.ENOENT:
                pytest.skip("Redis is not installed.")
            else:
                raise

        yield
        xprocess.getinfo("redis_server").terminate()

    @pytest.fixture(params=(None, False, True))
    def make_cache(self, request):
        if request.param is None:
            host = "localhost"
        elif request.param:
            host = redis.StrictRedis()
        else:
            host = redis.Redis()

        c = cache.RedisCache(host=host, key_prefix="werkzeug-test-case:")
        yield lambda: c
        c.clear()

    def test_compat(self, c):
        assert c._client.set(c.key_prefix + "foo", "Awesome")
        assert c.get("foo") == b"Awesome"
        assert c._client.set(c.key_prefix + "foo", "42")
        assert c.get("foo") == 42

    def test_empty_host(self):
        with pytest.raises(ValueError) as exc_info:
            cache.RedisCache(host=None)
        assert text_type(exc_info.value) == "RedisCache host parameter may not be None"


class TestMemcachedCache(GenericCacheTests):
    _can_use_fast_sleep = False
    _guaranteed_deletes = False

    @pytest.fixture(scope="class", autouse=True)
    def requirements(self, xprocess):
        if memcache is None:
            pytest.skip(
                "Python package for memcache is not installed. Need one of "
                '"pylibmc", "google.appengine", or "memcache".'
            )

        def prepare(cwd):
            return "", ["memcached"]

        try:
            xprocess.ensure("memcached", prepare)
        except IOError as e:
            # xprocess raises FileNotFoundError
            if e.errno == errno.ENOENT:
                pytest.skip("Memcached is not installed.")
            else:
                raise

        yield
        xprocess.getinfo("memcached").terminate()

    @pytest.fixture
    def make_cache(self):
        c = cache.MemcachedCache(key_prefix="werkzeug-test-case:")
        yield lambda: c
        c.clear()

    def test_compat(self, c):
        assert c._client.set(c.key_prefix + "foo", "bar")
        assert c.get("foo") == "bar"

    def test_huge_timeouts(self, c):
        # Timeouts greater than epoch are interpreted as POSIX timestamps
        # (i.e. not relative to now, but relative to epoch)
        epoch = 2592000
        c.set("foo", "bar", epoch + 100)
        assert c.get("foo") == "bar"


class TestUWSGICache(GenericCacheTests):
    _can_use_fast_sleep = False
    _guaranteed_deletes = False

    @pytest.fixture(scope="class", autouse=True)
    def requirements(self):
        try:
            import uwsgi  # NOQA
        except ImportError:
            pytest.skip(
                'Python "uwsgi" package is only avaialable when running '
                "inside uWSGI."
            )

    @pytest.fixture
    def make_cache(self):
        c = cache.UWSGICache(cache="werkzeugtest")
        yield lambda: c
        c.clear()


class TestNullCache(CacheTestsBase):
    @pytest.fixture(scope="class", autouse=True)
    def make_cache(self):
        return cache.NullCache

    def test_has(self, c):
        assert not c.has("foo")
