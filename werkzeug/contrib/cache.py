# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.cache
    ~~~~~~~~~~~~~~~~~~~~~~

    Small helper module that provides a simple interface to memcached, a
    simple django-inspired in-process cache and a file system based cache.

    The idea is that it's possible to switch caching systems without changing
    much code in the application.


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
from itertools import izip
from time import time
from cPickle import loads, dumps, load, dump, HIGHEST_PROTOCOL

have_memcache = True
try:
    from cmemcache import memcache
except ImportError:
    try:
        import memcache
    except ImportError:
        have_memcache = False


class BaseCache(object):
    """Baseclass for the cache systems."""

    def __init__(self, default_timeout=300):
        self.default_timeout = default_timeout

    def get(self, key):
        return None
    delete = get

    def get_many(self, *keys):
        return [self.get(key) for key in keys]

    def get_dict(self, *keys):
        return dict(izip(keys, self.get_many(keys)))

    def set(self, key, value, timeout=None):
        pass
    add = set

    def set_many(self, mapping, timeout=None):
        for key, value in mapping.iteritems():
            self.set(key, value, timeout)

    def delete_many(self, *keys):
        for key in keys:
            self.delete(key)

    def clear(self):
        pass


class NullCache(BaseCache):
    """A cache that doesn't cache."""


class SimpleCache(BaseCache):
    """
    Simple memory cache for single process environments.  This class exists
    mainly for the development server and is not 100% thread safe.  It tries
    to use as many atomic operations as possible and no locks for simplicity
    but it could happen under heavy load that keys are added multiple times.
    """

    def __init__(self, threshold=500, default_timeout=300):
        BaseCache.__init__(self, default_timeout)
        self._cache = {}
        self.clear = self._cache.clear
        self._threshold = threshold

    def _prune(self):
        if len(self._cache) > self._threshold:
            now = time()
            for idx, (key, (expires, _)) in enumerate(self._cache.items()):
                if expires <= now or idx % 3 == 0:
                    self._cache.pop(key, None)

    def get(self, key):
        now = time()
        expires, value = self._cache.get(key, (0, None))
        if expires > time():
            return loads(value)

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        self._prune()
        self._cache[key] = (time() + timeout, dumps(value, HIGHEST_PROTOCOL))

    def add(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        if len(self._cache) > self._threshold:
            self._prune()
        item = (time() + timeout, dumps(value, HIGHEST_PROTOCOL))
        self._cache.setdefault(key, item)

    def delete(self, key):
        self._cache.pop(key, None)


class MemcachedCache(BaseCache):
    """A cache that uses memcached as backend."""

    def __init__(self, servers, default_timeout=300):
        BaseClient.__init__(self, default_timeout)
        self._client = memcache.Client(servers)

    def get(self, key):
        return self._client.get(key)

    def get_many(self, *keys):
        return self._client.get_multi(*keys)

    def add(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        self._client.add(key, value, timeout)

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        self._client.set(key, value, timeout)

    def set_many(self, mapping, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        self._client.set_multi(mapping, timeout)

    def delete(self, key):
        self._client.delete(key)

    def delete_many(self, *keys):
        self._client.delete_multi(keys)

    def clear(self):
        self._client.flush_all()


class FileSystemCache(BaseCache):
    """A cache that stores the items on the file system."""

    def __init__(self, cache_dir, threshold=500, default_timeout=300):
        BaseCache.__init__(self, default_timeout)
        self._path = cache_dir
        self._threshold = threshold
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    def _prune(self):
        entries = os.listdir(self._path)
        if len(entries) > self._threshold:
            now = time()
            for idx, key in enumerate(entries):
                try:
                    f = file(self._get_filename(key))
                    if pickle.load(f) > now and idx % 3 != 0:
                        f.close()
                        continue
                except:
                    f.close()
                self.delete(key)

    def _get_filename(self, key):
        hash = md5(key).hexdigest()
        return os.path.join(self._path, hash)

    def get(self, key):
        filename = self._get_filename(key)
        try:
            f = file(filename, 'rb')
            try:
                if load(f) >= time():
                    return load(f)
            finally:
                f.close()
            os.remove(filename)
        except:
            return None

    def add(self, key, value, timeout=None):
        filename = self._get_filename(key)
        if not os.path.exists(filename):
            self.set(key, value, timeout)

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        filename = self._get_filename(key)
        self._prune()
        try:
            f = file(filename, 'wb')
            try:
                dump(int(time() + timeout), f, 1)
                dump(value, f, HIGHEST_PROTOCOL)
            finally:
                f.close()
        except (IOError, OSError):
            pass

    def delete(self, key):
        try:
            os.remove(self._get_filename(key))
        except (IOError, OSError):
            pass

    def clear(self):
        for key in os.listdir(self._path):
            self.delete(key)
