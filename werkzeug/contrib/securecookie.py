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

        from werkzeug import BaseRequest, cached_property
        from werkzeug.contrib.securecookie import SecureCookie

        # don' use this key but a different one.  you could just use
        # os.unrandom(20) to get something random
        SECRET_KEY = '\xfa\xdd\xb8z\xae\xe0}4\x8b\xea'

        class Request(BaseRequest):

            @cached_property
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
                                    httponly=True)
            return response(environ, start_response)


    :copyright: 2007 by Armin Ronacher, Thomas Johansson.
    :license: BSD, see LICENSE for more details.
"""
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
from hmac import new as hmac
from datetime import datetime
from time import time, mktime, gmtime
from random import Random
from cPickle import loads, dumps, HIGHEST_PROTOCOL
from werkzeug import url_quote_plus, url_unquote_plus
from werkzeug.contrib.sessions import ModificationTrackingDict, generate_key


class UnquoteError(Exception):
    pass


def pickle_quote(value):
    """Pickle and url encode a value."""
    result = None
    for protocol in xrange(HIGHEST_PROTOCOL + 1):
        data = ''.join(dumps(value, protocol).encode('base64').splitlines()).strip()
        if result is None or len(result) > len(data):
            result = data
    return result


def pickle_unquote(string):
    """URL decode a string and load it into pickle"""
    try:
        return loads(string.decode('base64'))
    # unfortunately pickle can cause pretty every error here.
    # if we get one we catch it and convert it into an UnquoteError
    except Exception, e:
        raise UnquoteError(str(e))


class SecureCookie(ModificationTrackingDict):
    """Represents a secure cookie.  You can subclass this class and provide
    an alternative mac method.  The import thing is that the mac method
    is a function with a similar interface to the hashlib.  Required
    methods are update() and digest().
    """

    hash_method = sha1

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
        return self.modified
    should_save = property(should_save)

    def serialize(self, expires=None):
        """Serialize the secure cookie into a string.

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
        mac = hmac(self.secret_key, None, self.hash_method)
        for key, value in self.iteritems():
            result.append('%s=%s' % (
                url_quote_plus(key),
                pickle_quote(value)
            ))
            mac.update('|' + result[-1])
        return '%s?%s' % (
            mac.digest().encode('base64').strip(),
            '&'.join(result)
        )

    def unserialize(cls, string, secret_key):
        """Load the secure cookie from a serialized string."""
        if isinstance(string, unicode):
            string = string.encode('utf-8', 'ignore')
        try:
            base64_hash, data = string.split('?', 1)
        except (ValueError, IndexError):
            items = ()
        else:
            items = {}
            mac = hmac(secret_key, None, cls.hash_method)
            for item in data.split('&'):
                mac.update('|' + item)
                if not '=' in item:
                    items = None
                    break
                key, value = item.split('=', 1)
                # try to make the key a string
                key = url_unquote_plus(key)
                try:
                    key = str(key)
                except UnicodeError:
                    pass
                items[key] = value

            # no parsing error and the mac looks okay, we can now
            # sercurely unpickle our cookie.
            try:
                client_hash = base64_hash.decode('base64')
            except Exception:
                items = client_hash = None
            if items is not None and client_hash == mac.digest():
                try:
                    for key, value in items.iteritems():
                        items[key] = pickle_unquote(value)
                except UnquoteError:
                    items = ()
                else:
                    if '_expires' in items:
                        if time() > items['_expires']:
                            items = ()
                        else:
                            del items['_expires']
            else:
                items = ()
        return cls(items, secret_key, False)
    unserialize = classmethod(unserialize)

    def load_cookie(cls, request, key='session', secret_key=None):
        """Loads a SecureCookie from a cookie in request. If the cookie is not
        set, a new SecureCookie instanced is returned.
        """
        data = request.cookies.get(key)
        if not data:
            return SecureCookie(secret_key=secret_key)
        return SecureCookie.unserialize(data, secret_key)
    load_cookie = classmethod(load_cookie)

    def save_cookie(self, response, key='session', expires=None,
                    session_expires=None, max_age=None, path='/', domain=None,
                    secure=None, httponly=False, force=False):
        """Saves the SecureCookie in a cookie on response."""
        if force or self.should_save:
            data = self.serialize(session_expires or expires)
            response.set_cookie(key, data, expires=expires, max_age=max_age,
                                path=path, domain=domain, secure=secure,
                                httponly=httponly)
