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

from werkzeug.wrappers import Response


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
        if isinstance(salt, unicode):
            salt = salt.encode('utf-8')
        h = hmac.new(salt, None, _hash_mods[method])
    else:
        if method not in _hash_funcs:
            return None
        h = _hash_funcs[method]()
    if isinstance(password, unicode):
        password = password.encode('utf-8')
    h.update(password)
    return h.hexdigest()


def generate_password_hash(password, method='sha1', salt_length=8):
    """Hash a password with the given method and salt with with a string of
    the given length.  The format of the string returned includes the method
    that was used so that :func:`check_password_hash` can check the hash.

    The format for the hashed string looks like this::

        method$salt$hash

    This method can **not** generate unsalted passwords but it is possible
    to set the method to plain to enforce plaintext passwords.  If a salt
    is used, hmac is used internally to salt the password.

    :param password: the password to hash
    :param method: the hash method to use (``'md5'`` or ``'sha1'``)
    :param salt_length: the lengt of the salt in letters
    """
    salt = method != 'plain' and gen_salt(salt_length) or ''
    h = _hash_internal(method, salt, password)
    if h is None:
        raise TypeError('invalid method %r' % method)
    return '%s$%s$%s' % (method, salt, h)


def check_password_hash(pwhash, password):
    """check a password against a given salted and hashed password value.
    In order to support unsalted legacy passwords this method supports
    plain text passwords, md5 and sha1 hashes (both salted and unsalted).

    Returns `True` if the password matched, `False` otherwise.

    :param pwhash: a hashed string like returned by
                   :func:`generate_password_hash`
    :param password: the plaintext password to compare against the hash
    """
    if pwhash.count('$') < 2:
        return False
    method, salt, hashval = pwhash.split('$', 2)
    return _hash_internal(method, salt, password) == hashval


def gen_nonce(length):
    nonce = ''.join(chr(_sys_rng.randint(16, 255)) for _ in xrange(length))
    return nonce.encode("hex")


class Authenticator(object):
    """An object which can validate HTTP authentication attempts and issue
    appropriate challenges in response.
    """

    def __init__(self, users=None):
        """Create an authenticator.

        ``users`` is an optional dictionary of usernames to passwords which
        can be provided for authentication.
        """

        self.users = users

    def password_for_user(self, user):
        """Retrieve a password for a certain user."""

        if user in self.users:
            return self.users[user]

        return None

    def make_basic_challenge(self, realm, message=None):
        """Create a HTTP basic authentication challenge."""

        if message is None:
            message = "Authentication is required"

        authenticate = 'Basic realm="%s"' % realm

        return Response(message, 401, {"WWW-Authenticate": authenticate})

    def make_digest_challenge(self, realm, message=None):
        """Create a HTTP digest authentication challenge."""

        if message is None:
            message = "Authentication is required"

        param_dict = {
            "realm": realm,
            "nonce": gen_nonce(16),
            "opaque": gen_nonce(16),
        }

        parameters = ", ".join('%s="%s"' % t for t in param_dict.items())

        authenticate = "Digest %s" % parameters

        return Response(message, 401, {"WWW-Authenticate": authenticate})

    def validate(self, authorization, method="GET"):
        """Validate an authorization.

        ``authorization`` is an ``Authorization`` object.

        ``method`` should be the actual method used, for HTTP digests.
        """

        if authorization.type == "basic":
            username = authorization.username
            expected = self.password_for_user(username)
            if expected is None:
                return False
            return expected == authorization.password

        if authorization.type == "digest":
            username = authorization.username
            password = self.password_for_user(username)
            if password is None:
                return False

            # Prepare the digest. RFCs 2069 and 2617 will be helpful in
            # explaining what everything is, but hopefully this is just as
            # self-explanatory.
            md5 = _hash_funcs["md5"]
            a1 = ":".join([authorization.username, authorization.realm,
                password])
            ha1 = md5(a1).hexdigest()
            a2 = ":".join([method, authorization.uri])
            ha2 = md5(a2).hexdigest()
            a3 = ":".join([ha1, authorization.nonce, ha2])
            expected = md5(a3).hexdigest()
            return expected == authorization.response

        return False
