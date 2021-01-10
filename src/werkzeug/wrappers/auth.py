import typing as t

from ..datastructures import Authorization
from ..datastructures import EnvironHeaders
from ..datastructures import Headers
from ..datastructures import WWWAuthenticate
from ..http import parse_authorization_header
from ..http import parse_www_authenticate_header
from ..utils import cached_property


class AuthorizationMixin:
    """Adds an :attr:`authorization` property that represents the parsed
    value of the `Authorization` header as
    :class:`~werkzeug.datastructures.Authorization` object.
    """

    headers: EnvironHeaders

    @cached_property
    def authorization(self) -> t.Optional[Authorization]:
        """The `Authorization` object in parsed form."""
        return parse_authorization_header(self.headers.get("Authorization"))


class WWWAuthenticateMixin:
    """Adds a :attr:`www_authenticate` property to a response object."""

    headers: Headers

    @property
    def www_authenticate(self) -> WWWAuthenticate:
        """The `WWW-Authenticate` header in a parsed form."""

        def on_update(www_auth: WWWAuthenticate) -> None:
            if not www_auth and "www-authenticate" in self.headers:
                del self.headers["www-authenticate"]
            elif www_auth:
                self.headers["WWW-Authenticate"] = www_auth.to_header()

        header = self.headers.get("www-authenticate")
        return parse_www_authenticate_header(header, on_update)
