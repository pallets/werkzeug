# -*- coding: utf-8 -*-
r"""
    werkzeug.contrib.securecookie
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module implements a cookie that is not alterable from the client
    because it adds a checksum the server checks for.  You can use it as
    session replacement if all you have is a user id or something to mark
    a logged in user.

    Keep in mind that the data is still readable from the client as a
    normal cookie is.  However you don't have to store and flush the
    sessions you have at the server.

    Example usage:

        >>> from werkzeug.contrib.securecookie import SecureCookie
        >>> x = SecureCookie({"foo": 42, "baz": (1, 2, 3)}, "deadbeef")

    Dumping into a string so that one can store it in a cookie:

        >>> value = x.serialize()

    Loading from that string again:

        >>> x = SecureCookie.unserialize(value, "deadbeef")
        >>> x["baz"]
        (1, 2, 3)

    If someone modifies the cookie and the checksum is wrong the unserialize
    method will fail silently and return a new empty `SecureCookie` object.

    Keep in mind that the values will be visible in the cookie so do not
    store data in a cookie you don't want the user to see.

    Application Integration
    =======================

    If you are using the werkzeug request objects you could integrate the
    secure cookie into your application like this::

        from werkzeug import BaseRequest, lazy_property
        from werkzeug.contrib.securecookie import SecureCookie

        # don' use this key but a different one.  you could just use
        # os.unrandom(20) to get something random
        SECRET_KEY = '\xfa\xdd\xb8z\xae\xe0}4\x8b\xea'

        class Request(BaseRequest):

            @lazy_property
            def client_session(self):
                data = self.cookies.get('session_data')
                if not data:
                    return SecureCookie(secret_key=SECRET_KEY)
                return SecureCookie.unserialize(data, SECRET_KEY)

        def application(environ, start_response):
            request = Request(environ, start_response)

            # get a response object here
            response = ...

            if request.client_session.should_save:
                session_data = request.client_session.serialize()
                response.set_cookie('session_data', session_data,
                                    http_only=True)
            return response(environ, start_response)


    :copyright: 2007 by Armin Ronacher, Thomas Johansson.
    :license: BSD, see LICENSE for more details.
"""
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
import urllib
from datetime import datetime
from time import time, mktime
from random import Random
from cPickle import loads, dumps, UnpicklingError
from werkzeug import url_quote_plus, url_unquote_plus
from werkzeug.contrib.sessions import ModificationTrackingDict


def pickle_quote(value):
    """Pickle and url encode a value."""
    return urllib.quote_plus(dumps(value, 1))


def pickle_unquote(string):
    """URL decode a string and load it into pickle"""
    try:
        return loads(urllib.unquote_plus(string))
    except UnpicklingError:
        return None


class SecureCookie(ModificationTrackingDict):
    """
    Represents a secure cookie.
    """
    __slots__ = ModificationTrackingDict.__slots__ + ('secret_key', 'new')

    def __init__(self, data=None, secret_key=None, new=True):
        ModificationTrackingDict.__init__(self, data or ())
        self.secret_key = secret_key
        self.new = new

    def __repr__(self):
        return '<%s %s%s>' % (
            self.__class__.__name__,
            dict.__repr__(self),
            self.should_save and '*' or ''
        )

    def should_save(self):
        """True if the session should be saved."""
        return self.modified or self.new
    should_save = property(should_save)

    def new_salt(self, secret_key):
        """Return a new salt."""
        return sha1('%s|%s' % (Random(secret_key).random(), time())). \
                    hexdigest()[:5]

    def serialize(self, expires=None):
        """
        Serialize the secure cookie into a string.

        If expires is provided, the session will be automatically invalidated
        after expiration when you unseralize it. This provides better
        protection against session cookie theft.
        """
        if self.secret_key is None:
            raise RuntimeError('no secret key defined')
        if expires:
            if isinstance(expires, datetime):
                expires = expires.utctimetuple()
            elif isinstance(expires, (int, long, float)):
                expires = gmtime(expires)
            self['_expires'] = int(mktime(expires))
        result = []
        salt = self.new_salt(self.secret_key)
        hash = sha1(self.secret_key + '|' + salt)
        for key, value in self.iteritems():
            result.append('%s=%s' % (
                url_quote_plus(key),
                pickle_quote(value)
            ))
            hash.update('|' + result[-1])
        return '%s?%s?%s' % (
            salt,
            hash.hexdigest(),
            '&'.join(result)
        )

    def unserialize(cls, string, secret_key):
        """Load the secure cookie from a serialized string."""
        if isinstance(string, unicode):
            string = string.encode('utf-8', 'ignore')
        try:
            salt, client_hash, data = string.split('?', 2)
        except (ValueError, IndexError):
            items = ()
        else:
            items = {}
            hash = sha1(secret_key + '|' + salt)
            for item in data.split('&'):
                hash.update('|' + item)
                if not '=' in item:
                    items = None
                    break
                key, value = item.split('=', 1)
                items[url_unquote_plus(key)] = value

            # no parsing error and the hash looks okay, we can now
            # sercurely unpickle our cookie.
            if items is not None and client_hash == hash.hexdigest():
                for key, value in items.iteritems():
                    items[key] = pickle_unquote(value)
                if '_expires' in items:
                    if time() > items['_expires']:
                        items = ()
                    else:
                        del items['_expires']
            else:
                items = ()
        return cls(items, secret_key, False)
    unserialize = classmethod(unserialize)
