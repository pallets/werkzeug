from werkzeug.contrib.cache import SimpleCache

def test_simplecache_get_dict():
    cache = SimpleCache()
    cache.set('a', 'a')
    cache.set('b', 'b')
    d = cache.get_dict('a', 'b')
    assert 'a' in d
    assert 'a' == d['a']
    assert 'b' in d
    assert 'b' == d['b']
