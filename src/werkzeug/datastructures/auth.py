from __future__ import annotations

import base64
import binascii
import collections.abc as cabc
import typing as t

from ..http import dump_header
from ..http import parse_dict_header
from ..http import quote_header_value
from .structures import CallbackDict

if t.TYPE_CHECKING:
    import typing_extensions as te


class Authorization:
    """A parsed ``Authorization`` header.

    :attr:`.Request.authorization` returns an instance if the header is set.

    An instance can be used with the test :class:`.Client` request methods' ``auth``
    parameter to send the header in test requests.

    Depending on the auth scheme, either :attr:`parameters` or :attr:`token` will be
    set. The ``Basic`` scheme's token is decoded into the ``username`` and ``password``
    parameters.

    .. versionchanged:: 3.2
        Get/set/delete ``auth["key"]`` and ``auth.key``, along with
        ``"key" in auth`` and ``auth.get("key")``, are deprecated and will
        be removed in Werkzeug 3.3. Use ``parameters`` directly instead.

    .. versionchanged:: 2.3
        The ``token`` parameter and attribute was added to support auth schemes
        that use a token instead of parameters, such as ``Bearer``.

    .. versionchanged:: 2.3
        The object is no longer a ``dict``.

    .. versionchanged:: 0.5
        The object is an immutable dict.
    """

    def __init__(
        self,
        auth_type: str,
        data: dict[str, str | None] | None = None,
        token: str | None = None,
    ) -> None:
        self.type = auth_type
        """The authorization scheme, like ``basic``, ``digest``, or ``bearer``."""

        if data is None:
            data = {}

        self.parameters = data
        """A dict of parameters parsed from the header. Either this or :attr:`token`
        will have a value for a given scheme.
        """

        self.token = token
        """A token parsed from the header. Either this or :attr:`parameters` will have a
        value for a given scheme.

        .. versionadded:: 2.3
        """

    @property
    def username(self) -> str | None:
        """The ``username`` key from :attr:`parameters`. A shortcut for
        ``Basic`` auth.
        """
        return self.parameters.get("username")

    @property
    def password(self) -> str | None:
        """The ``password`` key from :attr:`parameters`. A shortcut for
        ``Basic`` auth.
        """
        return self.parameters.get("password")

    def __getattr__(self, name: str) -> str | None:
        import warnings

        warnings.warn(
            f"'auth.{name}' is deprecated and will be removed in Werkzeug 3.3."
            f" Use 'auth.parameters[\"{name}\"]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parameters.get(name)

    def __getitem__(self, name: str) -> str | None:
        import warnings

        warnings.warn(
            "'auth[key]' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'auth.parameters[key]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parameters.get(name)

    def get(self, key: str, default: str | None = None) -> str | None:
        import warnings

        warnings.warn(
            "'auth.get(key)' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'auth.parameters.get(key)' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parameters.get(key, default)

    def __contains__(self, key: str) -> bool:
        import warnings

        warnings.warn(
            "'key in auth' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'key in auth.parameters' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return key in self.parameters

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Authorization):
            return NotImplemented

        return (
            other.type == self.type
            and other.token == self.token
            and other.parameters == self.parameters
        )

    @classmethod
    def from_header(cls, value: str | None) -> te.Self | None:
        """Parse an ``Authorization`` header value and create an instance of
        this class, or ``None`` if the value is empty.

        :param value: The header value to parse.

        .. versionadded:: 2.3
        """
        if not value:
            return None

        scheme, _, rest = value.partition(" ")
        scheme = scheme.lower()
        rest = rest.strip(" \t")

        if scheme == "basic":
            try:
                username, _, password = (
                    base64.b64decode(rest, validate=True).decode().partition(":")
                )
            except (binascii.Error, UnicodeError):
                return None

            return cls(scheme, {"username": username, "password": password})

        if "=" in rest.rstrip("="):
            # = that is not trailing, this is parameters.
            return cls(scheme, parse_dict_header(rest), None)

        # No = or only trailing =, this is a token.
        return cls(scheme, None, rest)

    def to_header(self) -> str:
        """Convert to an ``Authorization`` header value.

        .. versionadded:: 2.0
        """
        if self.type == "basic":
            value = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode("ascii")
            return f"Basic {value}"

        if self.token is not None:
            return f"{self.type.title()} {self.token}"

        return f"{self.type.title()} {dump_header(self.parameters)}"

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.to_header()}>"


class WWWAuthenticate:
    """A parsed ``WWW-Authenticate`` header.

    Set :attr:`.Response.www_authenticate` to an instance or list of instances to set
    the header. Modifying the instance will update the header.

    Depending on the auth scheme, either :attr:`parameters` or :attr:`token` should be
    set. The ``Basic`` scheme will encode ``username`` and ``password`` parameters to a
    token.

    .. versionchanged:: 3.2
        Considered ``False`` if ``type`` is the empty string.

    .. versionchanged:: 3.2
        Get/set/delete ``auth["key"]`` and ``auth.key``, along with
        ``"key" in auth`` and ``auth.get("key")``, are deprecated and will
        be removed in Werkzeug 3.3. Use ``parameters`` directly instead.

    .. versionchanged:: 2.3
        The ``token`` parameter and attribute was added to support auth schemes
        that use a token instead of parameters, such as ``Bearer``.

    .. versionchanged:: 2.3
        The object is no longer a ``dict``.

    .. versionchanged:: 2.3
        The ``on_update`` parameter was removed.
    """

    def __init__(
        self,
        auth_type: str = "",
        values: dict[str, str | None] | None = None,
        token: str | None = None,
    ):
        self._type = auth_type.lower()
        self._parameters: dict[str, str | None] = CallbackDict(
            values, lambda _: self._trigger_on_update()
        )
        self._token = token
        self._on_update: cabc.Callable[[WWWAuthenticate], None] | None = None

    def _trigger_on_update(self) -> None:
        if self._on_update is not None:
            self._on_update(self)

    @property
    def type(self) -> str:
        """The authorization scheme, like ``basic``, ``digest``, or ``bearer``."""
        return self._type

    @type.setter
    def type(self, value: str) -> None:
        self._type = value
        self._trigger_on_update()

    @property
    def parameters(self) -> dict[str, str | None]:
        """A dict of parameters for the header. Only one of this or :attr:`token` should
        have a value for a given scheme.
        """
        return self._parameters

    @parameters.setter
    def parameters(self, value: dict[str, str]) -> None:
        self._parameters = CallbackDict(value, lambda _: self._trigger_on_update())
        self._trigger_on_update()

    @property
    def token(self) -> str | None:
        """A dict of parameters for the header. Only one of this or :attr:`token` should
        have a value for a given scheme.
        """
        return self._token

    @token.setter
    def token(self, value: str | None) -> None:
        """A token for the header. Only one of this or :attr:`parameters` should have a
        value for a given scheme.

        .. versionadded:: 2.3
        """
        self._token = value
        self._trigger_on_update()

    def __getitem__(self, key: str) -> str | None:
        import warnings

        warnings.warn(
            "'auth[key]' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'auth.parameters[key]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parameters.get(key)

    def __setitem__(self, key: str, value: str | None) -> None:
        import warnings

        warnings.warn(
            "'auth[key] = value' is deprecated and will be removed in"
            " Werkzeug 3.3. Use 'auth.parameters[key] = value' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if value is None:
            if key in self.parameters:
                del self.parameters[key]
        else:
            self.parameters[key] = value

        self._trigger_on_update()

    def __delitem__(self, key: str) -> None:
        import warnings

        warnings.warn(
            "'del auth[key]' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'del auth.parameters[key]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if key in self.parameters:
            del self.parameters[key]
            self._trigger_on_update()

    def __getattr__(self, name: str) -> str | None:
        import warnings

        warnings.warn(
            f"'auth.{name}' is deprecated and will be removed in Werkzeug 3.3."
            f" Use 'auth.parameters[\"{name}\"]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self[name]

    def __setattr__(self, name: str, value: str | None) -> None:
        if name in {
            "type",
            "_type",
            "parameters",
            "_parameters",
            "token",
            "_token",
            "_on_update",
        }:
            super().__setattr__(name, value)
        else:
            import warnings

            warnings.warn(
                f"'auth.{name} = value' is deprecated and will be removed in"
                f" Werkzeug 3.3. Use 'auth.parameters[\"{name}\"] = value' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self[name] = value

    def __delattr__(self, name: str) -> None:
        import warnings

        warnings.warn(
            f"'del auth.{name}' is deprecated and will be removed in Werkzeug 3.3."
            f" Use 'del auth.parameters[\"{name}\"]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        del self[name]

    def __contains__(self, key: str) -> bool:
        import warnings

        warnings.warn(
            "'key in auth' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'key in auth.parameters' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return key in self.parameters

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WWWAuthenticate):
            return NotImplemented

        return (
            other.type == self.type
            and other.token == self.token
            and other.parameters == self.parameters
        )

    def get(self, key: str, default: str | None = None) -> str | None:
        import warnings

        warnings.warn(
            "'auth.get(key)' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'auth.parameters.get(key)' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parameters.get(key, default)

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a ``WWW-Authenticate`` header value and create an instance of
        this class.

        :param value: The header value to parse.

        .. versionchanged:: 3.2
            Return an empty instance instead of ``None`` if the value is empty.

        .. versionadded:: 2.3
        """
        if not value:
            return cls()

        scheme, _, rest = value.partition(" ")
        scheme = scheme.lower()
        rest = rest.strip(" \t")

        if "=" in rest.rstrip("="):
            # = that is not trailing, this is parameters.
            return cls(scheme, parse_dict_header(rest))

        # No = or only trailing =, this is a token or empty.
        if rest:
            return cls(scheme, token=rest)

        return cls(scheme)

    def to_header(self) -> str:
        """Convert to a ``WWW-Authenticate`` header value.

        .. versionchanged:: 3.2
            Return the empty string if the instance is empty.
        """
        if not self:
            return ""

        if self.token is not None:
            return f"{self.type.title()} {self.token}"

        if not self.parameters:
            return self.type.title()

        if self.type == "digest":
            items = []

            for key, value in self.parameters.items():
                if key in {"realm", "domain", "nonce", "opaque", "qop"}:
                    value = quote_header_value(value, allow_token=False)
                else:
                    value = quote_header_value(value)

                items.append(f"{key}={value}")

            return f"Digest {', '.join(items)}"

        return f"{self.type.title()} {dump_header(self.parameters)}"

    def __bool__(self) -> bool:
        return self._type != ""

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.to_header()}>"
