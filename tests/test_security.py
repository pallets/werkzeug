# -*- coding: utf-8 -*-
"""
    werkzeug.security test
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
from werkzeug import generate_password_hash, check_password_hash



def test_password_hashing():
    """Test the password hashing and password hash checking"""
    hash1 = generate_password_hash('default')
    hash2 = generate_password_hash(u'default', method='sha1')
    assert hash1 != hash2
    assert check_password_hash(hash1, 'default')
    assert check_password_hash(hash2, 'default')
    assert hash1.startswith('sha1$')
    assert hash2.startswith('sha1$')

    fakehash = generate_password_hash('default', method='plain')
    assert fakehash == 'plain$$default'
    assert check_password_hash(fakehash, 'default')

    mhash = generate_password_hash(u'default', method='md5')
    assert mhash.startswith('md5$')
    assert check_password_hash(mhash, 'default')

    legacy = 'md5$$c21f969b5f03d33d43e04f8f136e7682'
    assert check_password_hash(legacy, 'default')

    legacy = u'md5$$c21f969b5f03d33d43e04f8f136e7682'
    assert check_password_hash(legacy, 'default')
