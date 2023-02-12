import base64

from .mixins import ImmutableDictMixin
from .mixins import UpdateDictMixin


class Authorization(ImmutableDictMixin, dict):
    """Represents an ``Authorization`` header sent by the client.

    This is returned by
    :func:`~werkzeug.http.parse_authorization_header`. It can be useful
    to create the object manually to pass to the test
    :class:`~werkzeug.test.Client`.

    .. versionchanged:: 0.5
        This object became immutable.
    """

    def __init__(self, auth_type, data=None):
        dict.__init__(self, data or {})
        self.type = auth_type

    @property
    def username(self):
        """The username transmitted.  This is set for both basic and digest
        auth all the time.
        """
        return self.get("username")

    @property
    def password(self):
        """When the authentication type is basic this is the password
        transmitted by the client, else `None`.
        """
        return self.get("password")

    @property
    def realm(self):
        """This is the server realm sent back for HTTP digest auth."""
        return self.get("realm")

    @property
    def nonce(self):
        """The nonce the server sent for digest auth, sent back by the client.
        A nonce should be unique for every 401 response for HTTP digest auth.
        """
        return self.get("nonce")

    @property
    def uri(self):
        """The URI from Request-URI of the Request-Line; duplicated because
        proxies are allowed to change the Request-Line in transit.  HTTP
        digest auth only.
        """
        return self.get("uri")

    @property
    def nc(self):
        """The nonce count value transmitted by clients if a qop-header is
        also transmitted.  HTTP digest auth only.
        """
        return self.get("nc")

    @property
    def cnonce(self):
        """If the server sent a qop-header in the ``WWW-Authenticate``
        header, the client has to provide this value for HTTP digest auth.
        See the RFC for more details.
        """
        return self.get("cnonce")

    @property
    def response(self):
        """A string of 32 hex digits computed as defined in RFC 2617, which
        proves that the user knows a password.  Digest auth only.
        """
        return self.get("response")

    @property
    def opaque(self):
        """The opaque header from the server returned unchanged by the client.
        It is recommended that this string be base64 or hexadecimal data.
        Digest auth only.
        """
        return self.get("opaque")

    @property
    def qop(self):
        """Indicates what "quality of protection" the client has applied to
        the message for HTTP digest auth. Note that this is a single token,
        not a quoted list of alternatives as in WWW-Authenticate.
        """
        return self.get("qop")

    def to_header(self):
        """Convert to a string value for an ``Authorization`` header.

        .. versionadded:: 2.0
            Added to support passing authorization to the test client.
        """
        if self.type == "basic":
            value = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode("utf8")
            return f"Basic {value}"

        if self.type == "digest":
            return f"Digest {http.dump_header(self)}"

        raise ValueError(f"Unsupported type {self.type!r}.")


def auth_property(name, doc=None):
    """A static helper function for Authentication subclasses to add
    extra authentication system properties onto a class::

        class FooAuthenticate(WWWAuthenticate):
            special_realm = auth_property('special_realm')

    For more information have a look at the sourcecode to see how the
    regular properties (:attr:`realm` etc.) are implemented.
    """

    def _set_value(self, value):
        if value is None:
            self.pop(name, None)
        else:
            self[name] = str(value)

    return property(lambda x: x.get(name), _set_value, doc=doc)


def _set_property(name, doc=None):
    def fget(self):
        def on_update(header_set):
            if not header_set and name in self:
                del self[name]
            elif header_set:
                self[name] = header_set.to_header()

        return http.parse_set_header(self.get(name), on_update)

    return property(fget, doc=doc)


class WWWAuthenticate(UpdateDictMixin, dict):
    """Provides simple access to `WWW-Authenticate` headers."""

    #: list of keys that require quoting in the generated header
    _require_quoting = frozenset(["domain", "nonce", "opaque", "realm", "qop"])

    def __init__(self, auth_type=None, values=None, on_update=None):
        dict.__init__(self, values or ())
        if auth_type:
            self["__auth_type__"] = auth_type
        self.on_update = on_update

    def set_basic(self, realm="authentication required"):
        """Clear the auth info and enable basic auth."""
        dict.clear(self)
        dict.update(self, {"__auth_type__": "basic", "realm": realm})
        if self.on_update:
            self.on_update(self)

    def set_digest(
        self, realm, nonce, qop=("auth",), opaque=None, algorithm=None, stale=False
    ):
        """Clear the auth info and enable digest auth."""
        d = {
            "__auth_type__": "digest",
            "realm": realm,
            "nonce": nonce,
            "qop": http.dump_header(qop),
        }
        if stale:
            d["stale"] = "TRUE"
        if opaque is not None:
            d["opaque"] = opaque
        if algorithm is not None:
            d["algorithm"] = algorithm
        dict.clear(self)
        dict.update(self, d)
        if self.on_update:
            self.on_update(self)

    def to_header(self):
        """Convert the stored values into a WWW-Authenticate header."""
        d = dict(self)
        auth_type = d.pop("__auth_type__", None) or "basic"
        kv_items = (
            (k, http.quote_header_value(v, allow_token=k not in self._require_quoting))
            for k, v in d.items()
        )
        kv_string = ", ".join([f"{k}={v}" for k, v in kv_items])
        return f"{auth_type.title()} {kv_string}"

    def __str__(self):
        return self.to_header()

    def __repr__(self):
        return f"<{type(self).__name__} {self.to_header()!r}>"

    type = auth_property(
        "__auth_type__",
        doc="""The type of the auth mechanism. HTTP currently specifies
        ``Basic`` and ``Digest``.""",
    )
    realm = auth_property(
        "realm",
        doc="""A string to be displayed to users so they know which
        username and password to use. This string should contain at
        least the name of the host performing the authentication and
        might additionally indicate the collection of users who might
        have access.""",
    )
    domain = _set_property(
        "domain",
        doc="""A list of URIs that define the protection space. If a URI
        is an absolute path, it is relative to the canonical root URL of
        the server being accessed.""",
    )
    nonce = auth_property(
        "nonce",
        doc="""
        A server-specified data string which should be uniquely generated
        each time a 401 response is made. It is recommended that this
        string be base64 or hexadecimal data.""",
    )
    opaque = auth_property(
        "opaque",
        doc="""A string of data, specified by the server, which should
        be returned by the client unchanged in the Authorization header
        of subsequent requests with URIs in the same protection space.
        It is recommended that this string be base64 or hexadecimal
        data.""",
    )
    algorithm = auth_property(
        "algorithm",
        doc="""A string indicating a pair of algorithms used to produce
        the digest and a checksum. If this is not present it is assumed
        to be "MD5". If the algorithm is not understood, the challenge
        should be ignored (and a different one used, if there is more
        than one).""",
    )
    qop = _set_property(
        "qop",
        doc="""A set of quality-of-privacy directives such as auth and
        auth-int.""",
    )

    @property
    def stale(self):
        """A flag, indicating that the previous request from the client
        was rejected because the nonce value was stale.
        """
        val = self.get("stale")
        if val is not None:
            return val.lower() == "true"

    @stale.setter
    def stale(self, value):
        if value is None:
            self.pop("stale", None)
        else:
            self["stale"] = "TRUE" if value else "FALSE"

    auth_property = staticmethod(auth_property)


# circular dependencies
from .. import http
