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
import os
import re
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
from itertools import izip
from time import time
from cPickle import loads, dumps, load, dump, HIGHEST_PROTOCOL

have_memcache = True
try:
    import cmemcache as memcache
    is_cmemcache = True
except ImportError:
    try:
        import memcache
        is_cmemcache = False
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
        return map(self.get, keys)

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

    def inc(self, key, delta=1):
        self.set(key, (self.get(key) or 0) + delta)

    def dec(self, key, delta=1):
        self.set(key, (self.get(key) or 0) - delta)


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


_test_memcached_key = re.compile(r'[^\x00-\x21\xff]{1,250}$').match

class MemcachedCache(BaseCache):
    """
    A cache that uses memcached as backend.

    Implementation notes:  This cache backend works around some limitations in
    memcached to simplify the interface.  For example unicode keys are encoded
    to utf-8 on the fly.  Methods such as `get_dict` return the keys in the
    same format as passed.  Furthermore all get methods silently ignore key
    errors to not cause problems when untrusted user data is passed to the get
    methods which is often the case in web applications.
    """

    def __init__(self, servers, default_timeout=300):
        BaseCache.__init__(self, default_timeout)
        if not have_memcache:
            raise RuntimeError('no memcache module found')

        # cmemcache has a bug that debuglog is not defined for the
        # client.  Whenever pickle fails you get a weird AttributError.
        if is_cmemcache:
            self._client = memcache.Client(map(str, servers))
            try:
                self._client.debuglog = lambda *a: None
            except:
                pass
        else:
            self._client = memcache.Client(servers, False, HIGHEST_PROTOCOL)

    def get(self, key):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        # memcached doesn't support keys longer than that.  Because often
        # checks for so long keys can occour because it's tested from user
        # submitted data etc we fail silently for getting.
        if _test_memcached_key(key):
            return self._client.get(key)

    def get_dict(self, *keys):
        key_mapping = {}
        have_encoded_keys = False
        for idx, key in enumerate(keys):
            if isinstance(key, unicode):
                encoded_key = key.encode('utf-8')
                have_encoded_keys = True
            else:
                encoded_key = key
            if _test_memcached_key(key):
                key_mapping[encoded_key] = key
        # the keys call here is important because otherwise cmemcache
        # does ugly things.  What exaclty I don't know, i think it does
        # Py_DECREF but quite frankly i don't care.
        d = rv = self._client.get_multi(key_mapping.keys())
        if have_encoded_keys:
            rv = {}
            for key, value in d.iteritems():
                rv[key_mapping[key]] = value
        if len(rv) < len(keys):
            for key in keys:
                if key not in rv:
                    rv[key] = None
        return rv

    def add(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        self._client.add(key, value, timeout)

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        self._client.set(key, value, timeout)

    def get_many(self, *keys):
        d = self.get_dict(*keys)
        return [d[key] for key in keys]

    def set_many(self, mapping, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        new_mapping = {}
        for key, value in mapping.iteritems():
            if isinstance(key, unicode):
                key = key.encode('utf-8')
            new_mapping[key] = value
        self._client.set_multi(new_mapping, timeout)

    def delete(self, key):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        self._client.delete(key)

    def delete_many(self, *keys):
        keys = list(keys)
        for idx, key in enumerate(keys):
            if isinstance(key, unicode):
                keys[idx] = key.encode('utf-8')
        self._client.delete_multi(keys)

    def clear(self):
        self._client.flush_all()

    def inc(self, key, delta=1):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        self._client.incr(key, key, delta)

    def dec(self, key, delta=1):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        self._client.decr(key, key, delta)


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
