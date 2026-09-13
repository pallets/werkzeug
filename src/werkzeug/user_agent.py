from __future__ import annotations

import typing as t
from typing import Any


class _UserAgent(str):
    """Represents a parsed user agent header value.

    The default implementation does no parsing, only the :attr:`string`
    attribute is set. A subclass may parse the string to set the
    common attributes or expose other information. Set
    :attr:`werkzeug.wrappers.Request.user_agent_class` to use a
    subclass.

    :param string: The header value to parse.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 3.3. ``Request.user_agent`` is a string and
        can be parsed directly if needed.

    .. versionadded:: 2.0
        This replaces the previous ``useragents`` module, but does not
        provide a built-in parser.
    """

    platform: str | None = None
    """The OS name, if it could be parsed from the string."""

    browser: str | None = None
    """The browser name, if it could be parsed from the string."""

    version: str | None = None
    """The browser version, if it could be parsed from the string."""

    language: str | None = None
    """The browser language, if it could be parsed from the string."""

    @property
    def string(self) -> str:
        """The original header value."""
        return str(self)

    def to_header(self) -> str:
        """Convert to a header value."""
        return str(self)

    def __getattribute__(self, name: str, /) -> Any:
        if hasattr(str, name):
            return super().__getattribute__(name)

        import warnings

        warnings.warn(
            "The 'UserAgent' class is deprecated and will be removed in"
            " Werkzeug 3.3. 'Request.user_agent' is a string and can be"
            " parsed directly if needed.",
            DeprecationWarning,
            stacklevel=2,
        )
        return object.__getattribute__(self, name)


if not t.TYPE_CHECKING:

    def __getattr__(name: str) -> t.Any:
        if name == "UserAgent":
            import warnings

            warnings.warn(
                "The 'UserAgent' class is deprecated and will be removed in"
                " Werkzeug 3.3. 'Request.user_agent' is a string and can be"
                " parsed directly if needed.",
                DeprecationWarning,
                stacklevel=2,
            )
            return _UserAgent

        raise AttributeError(name)
