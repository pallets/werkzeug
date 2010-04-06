# -*- coding: utf-8 -*-
"""
    werkzeug.security
    ~~~~~~~~~~~~~~~~~

    Security related helpers such as secure password hashing tools.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import hmac
import string
from random import SystemRandom

# because the API of hmac changed with the introduction of the
# new hashlib module, we have to support both.  This sets up a
# mapping to the digest factory functions and the digest modules
# (or factory functions with changed API)
try:
    from hashlib import sha1, md5
    _hash_funcs = _hash_mods = {'sha1': sha1, 'md5': md5}
    _sha1_mod = sha1
    _md5_mod = md5
except ImportError:
    import sha as _sha1_mod, md5 as _md5_mod
    _hash_mods = {'sha1': _sha1_mod, 'md5': _md5_mod}
    _hash_funcs = {'sha1': _sha1_mod.new, 'md5': _md5_mod.new}


SALT_CHARS = string.letters + string.digits


_sys_rng = SystemRandom()


def gen_salt(length):
    """Generate a random string of SALT_CHARS with specified ``length``."""
    if length <= 0:
        raise ValueError('requested salt of length <= 0')
    return ''.join(_sys_rng.choice(SALT_CHARS) for _ in xrange(length))


def _hash_internal(method, salt, password):
    """Internal password hash helper.  Supports plaintext without salt,
    unsalted and salted passwords.  In case salted passwords are used
    hmac is used.
    """
    if method == 'plain':
        return password
    if salt:
        if method not in _hash_mods:
            return None
        h = hmac.new(salt, None, _hash_mods[method])
    else:
        if method not in _hash_funcs:
            return None
        h = _hash_funcs[method]()
    h.update(password)
    return h.hexdigest()


def generate_password_hash(password, method='sha1', salt_length=8):
    """return a the password encrypted in sha1 format with a random salt."""
    if isinstance(password, unicode):
        password = password.encode('utf-8')
    salt = method != 'plain' and gen_salt(salt_length) or ''
    h = _hash_internal(method, salt, password)
    if h is None:
        raise TypeError('invalid method %r' % method)
    return '%s$%s$%s' % (method, salt, h)


def check_password_hash(pwhash, password):
    """check a password against a given salted and hashed password value.
    In order to support unsalted legacy passwords this method supports
    plain text passwords, md5 and sha1 hashes (both salted and unsalted).
    """
    if isinstance(password, unicode):
        password = password.encode('utf-8')
    if pwhash.count('$') < 2:
        return False
    method, salt, hashval = pwhash.split('$', 2)
    return _hash_internal(method, salt, password) == hashval
