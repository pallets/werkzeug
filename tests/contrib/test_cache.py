import os, tempfile, shutil

from werkzeug.contrib.cache import SimpleCache, FileSystemCache, RedisCache


def test_simplecache_get_dict():
    """SimpleCache.get_dict bug"""
    cache = SimpleCache()
    cache.set('a', 'a')
    cache.set('b', 'b')
    d = cache.get_dict('a', 'b')
    assert 'a' in d
    assert 'a' == d['a']
    assert 'b' in d
    assert 'b' == d['b']


def test_filesystemcache_set_get():
    """
    test if FileSystemCache.set/get works
    """
    tmp_dir = tempfile.mkdtemp()
    try:
        cache = FileSystemCache(cache_dir=tmp_dir)
        for i in range(3):
            cache.set(str(i), i * i)
        for i in range(3):
            result = cache.get(str(i))
            assert result == i * i
    finally:
        shutil.rmtree(tmp_dir)


def test_filesystemcache_prune():
    """
    test if FileSystemCache._prune works and keeps the cache entry count
    below the given threshold.
    """
    THRESHOLD = 13
    tmp_dir = tempfile.mkdtemp()
    cache = FileSystemCache(cache_dir=tmp_dir, threshold=THRESHOLD)
    for i in range(2 * THRESHOLD):
        cache.set(str(i), i)
    cache_files = os.listdir(tmp_dir)
    shutil.rmtree(tmp_dir)
    assert len(cache_files) <= THRESHOLD


def test_filesystemcache_clear():
    """
    test if FileSystemCache.clear works
    """
    tmp_dir = tempfile.mkdtemp()
    cache = FileSystemCache(cache_dir=tmp_dir)
    cache.set('foo', 'bar')
    cache_files = os.listdir(tmp_dir)
    assert len(cache_files) == 1
    cache.clear()
    cache_files = os.listdir(tmp_dir)
    assert len(cache_files) == 0
    shutil.rmtree(tmp_dir)


def test_rediscache_get_set():
    """
    test basic RedisCache capabilities
    """
    cache = RedisCache()
    cache.set('foo', 'bar')
    assert cache.get('foo') == 'bar'


def test_rediscache_expire():
    """
    test RedisCache handling expire time on keys
    """
    import time
    cache = RedisCache()
    cache.set('foo', 'bar', 1)
    time.sleep(2)
    assert cache.get('foo') is None


def test_rediscache_add():
    """
    test if RedisCache.add() preserves existing keys
    """
    cache = RedisCache()
    # sanity check that add() works like set()
    cache.add('foo', 'bar')
    assert cache.get('foo') ==  'bar'
    cache.add('foo', 'qux')
    assert cache.get('foo') ==  'bar'


def test_rediscache_delete():
    """
    test if RedisCache correctly deletes single key
    """
    cache = RedisCache()
    cache.add('foo', 'bar')
    assert cache.get('foo') ==  'bar'
    cache.delete('foo')
    assert cache.get('foo') is None


def test_rediscache_delete_many():
    """
    test if RedisCache correctly deletes many keys
    """
    cache = RedisCache()
    cache.add('foo', 'bar')
    cache.add('spam', 'eggs')
    cache.delete_many('foo', 'spam')
    assert cache.get('foo') is None
    assert cache.get('spam') is None

