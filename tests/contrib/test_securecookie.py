from werkzeug.contrib.securecookie import SecureCookie


def test_basic_support():
    """Basid SecureCookie support"""
    c = SecureCookie(secret_key='foo')
    assert c.new
    print c.modified, c.should_save
    assert not c.modified
    assert not c.should_save
    c['x'] = 42
    assert c.modified
    assert c.should_save
    s = c.serialize()

    c2 = SecureCookie.unserialize(s, 'foo')
    assert not c2.new
    assert not c2.modified
    assert not c2.should_save
    assert c2 == c

    c3 = SecureCookie.unserialize(s, 'wrong foo')
    assert not c3.modified
    assert not c3.new
    assert c3 == {}
