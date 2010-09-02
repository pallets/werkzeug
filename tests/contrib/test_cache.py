import os, tempfile, shutil

from werkzeug.contrib.cache import SimpleCache, FileSystemCache


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

