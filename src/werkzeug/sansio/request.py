from __future__ import annotations

import collections.abc as cabc
import typing as t
from datetime import datetime
from urllib.parse import parse_qsl

from .._header_property import header_property
from ..datastructures.accept import Accept
from ..datastructures.accept import LanguageAccept
from ..datastructures.accept import MIMEAccept
from ..datastructures.auth import Authorization
from ..datastructures.cache_control import RequestCacheControl
from ..datastructures.etag import ETagSet
from ..datastructures.headers import Headers
from ..datastructures.range import IfRange
from ..datastructures.range import Range
from ..datastructures.set import HeaderSet
from ..datastructures.structures import ImmutableMultiDict
from ..http import parse_date
from ..http import parse_list_header
from ..http import parse_options_header
from ..http import SecFetchDest
from ..http import SecFetchMode
from ..http import SecFetchSite
from ..user_agent import _UserAgent
from ..utils import cached_property
from .http import parse_cookie
from .utils import get_content_length
from .utils import get_current_url
from .utils import get_host


class Request:
    """Represents the non-IO parts of a HTTP request, including the
    method, URL info, and headers.

    This class is not meant for general use. It should only be used when
    implementing WSGI, ASGI, or another HTTP application spec. Werkzeug
    provides a WSGI implementation at :cls:`werkzeug.wrappers.Request`.

    :param method: The method the request was made with, such as
        ``GET``.
    :param scheme: The URL scheme of the protocol the request used, such
        as ``https`` or ``wss``.
    :param server: The address of the server. ``(host, port)``,
        ``(path, None)`` for unix sockets, or ``None`` if not known.
    :param root_path: The prefix that the application is mounted under.
        This is prepended to generated URLs, but is not part of route
        matching.
    :param path: The path part of the URL after ``root_path``.
    :param query_string: The part of the URL after the "?".
    :param headers: The headers received with the request.
    :param remote_addr: The address of the client sending the request.

    .. versionchanged:: 3.0
        The ``charset``, ``url_charset``, and ``encoding_errors`` attributes
        were removed.

    .. versionadded:: 2.0
    """

    #: The class to use for :attr:`args`, :attr:`form`, and :attr:`files`.
    #:
    #: .. deprecated:: 3.2
    #:     Will be removed in Werkzeug 3.3. It will always be ``ImmutableMultiDict``.
    #:
    #: .. versionadded:: 0.6
    parameter_storage_class: None = None

    #: The class to use for parsed dict values, such as :attr:`cookies`.
    #:
    #: .. deprecated:: 3.2
    #:     Will be removed in Werkzeug 3.3. It will always be ``ImmutableMultiDict``.
    #:
    #: .. versionchanged:: 1.0.0
    #:     Changed to ``ImmutableMultiDict`` to support multiple values.
    #:
    #: .. versionadded:: 0.6
    dict_storage_class: None = None

    #: The class to use for parsed list values, such as :attr:`access_route`.
    #:
    #: .. deprecated:: 3.2
    #:     Will be removed in Werkzeug 3.3. It will always be ``Sequence``.
    #:
    #: .. versionadded:: 0.6
    list_storage_class: None = None

    user_agent_class: None = None
    """The class used and returned by the :attr:`user_agent` property to
    parse the header. Defaults to
    :class:`~werkzeug.user_agent.UserAgent`, which does no parsing. An
    extension can provide a subclass that uses a parser to provide other
    data.

    .. deprecated 3.2
        Will be removed in Werkzeug 3.3. ``user_agent`` is a string and can be
        parsed directly if needed.

    .. versionadded:: 2.0
    """

    #: Valid host names when handling requests. By default all hosts are
    #: trusted, which means that whatever the client says the host is
    #: will be accepted.
    #:
    #: Because ``Host`` and ``X-Forwarded-Host`` headers can be set to
    #: any value by a malicious client, it is recommended to either set
    #: this property or implement similar validation in the proxy (if
    #: the application is being run behind one).
    #:
    #: .. versionadded:: 0.9
    trusted_hosts: list[str] | None = None

    def __init__(
        self,
        method: str,
        scheme: str,
        server: tuple[str, int | None] | None,
        root_path: str,
        path: str,
        query_string: bytes,
        headers: Headers,
        remote_addr: str | None,
    ) -> None:
        #: The method the request was made with, such as ``GET``.
        self.method = method.upper()
        #: The URL scheme of the protocol the request used, such as
        #: ``https`` or ``wss``.
        self.scheme = scheme
        #: The address of the server. ``(host, port)``, ``(path, None)``
        #: for unix sockets, or ``None`` if not known.
        self.server = server
        #: The prefix that the application is mounted under, without a
        #: trailing slash. :attr:`path` comes after this.
        self.root_path = root_path.rstrip("/")
        #: The path part of the URL after :attr:`root_path`. This is the
        #: path used for routing within the application.
        self.path = "/" + path.lstrip("/")
        #: The part of the URL after the "?". This is the raw value, use
        #: :attr:`args` for the parsed values.
        self.query_string = query_string
        #: The headers received with the request.
        self.headers = headers
        #: The address of the client sending the request.
        self.remote_addr = remote_addr

    def __repr__(self) -> str:
        try:
            url = self.url
        except Exception as e:
            url = f"(invalid URL: {e})"

        return f"<{type(self).__name__} {url!r} [{self.method}]>"

    @cached_property
    def args(self) -> ImmutableMultiDict[str, str]:
        """The parsed URL query parameters (the ``?key=value&a=b`` part of a
        URL) as an :class:`ImmutableMultiDict`.

        .. versionchanged:: 2.3
            Invalid bytes remain percent encoded.
        """
        items = parse_qsl(
            self.query_string.decode(),
            keep_blank_values=True,
            errors="werkzeug.url_quote",
        )

        if self.parameter_storage_class is not None:
            import warnings

            warnings.warn(
                "Setting 'Request.parameter_storage_class' is deprecated and will be"
                " removed in Werkzeug 3.3. It will always be 'ImmutableMultiDict'.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.parameter_storage_class(items)

        return ImmutableMultiDict(items)

    @cached_property
    def access_route(self) -> cabc.Sequence[str]:
        """The route taken from the client to the application.

        This is ``X-Forwarded-For`` if it is set. Remember to only trust the
        last N values, where N is the number of servers setting this header in
        front of the application.

        Otherwise, this only contains :attr:`remote_addr`, or is empty.
        """
        if "X-Forwarded-For" in self.headers:
            items = tuple(parse_list_header(self.headers["X-Forwarded-For"]))
        elif self.remote_addr is not None:
            items = (self.remote_addr,)
        else:
            items = ()

        if self.list_storage_class is not None:
            import warnings

            warnings.warn(
                "Setting 'Request.list_storage_class' is deprecated and will be"
                " removed in Werkzeug 3.3. It will always be 'Sequence'.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.list_storage_class(items)

        return items

    @cached_property
    def full_path(self) -> str:
        """Requested path, including the query string."""
        return f"{self.path}?{self.query_string.decode()}"

    @cached_property
    def is_secure(self) -> bool:
        """``True`` if the request was made with a secure protocol
        (HTTPS or WSS).
        """
        return self.scheme in {"https", "wss"}

    @cached_property
    def url(self) -> str:
        """The full request URL with the scheme, host, root path, path,
        and query string."""
        return get_current_url(
            self.scheme, self.host, self.root_path, self.path, self.query_string
        )

    @cached_property
    def base_url(self) -> str:
        """Like :attr:`url` but without the query string."""
        return get_current_url(self.scheme, self.host, self.root_path, self.path)

    @cached_property
    def root_url(self) -> str:
        """The request URL scheme, host, and root path. This is the root
        that the application is accessed from.
        """
        return get_current_url(self.scheme, self.host, self.root_path)

    @cached_property
    def host_url(self) -> str:
        """The request URL scheme and host only."""
        return get_current_url(self.scheme, self.host)

    @cached_property
    def host(self) -> str:
        """The host name the request was made to, including the port if
        it's non-standard. Validated with :attr:`trusted_hosts`.

        See :func:`.get_host` for a detailed explanation.
        """
        return get_host(
            self.scheme, self.headers.get("Host"), self.server, self.trusted_hosts
        )

    @cached_property
    def cookies(self) -> ImmutableMultiDict[str, str]:
        """A :class:`dict` with the contents of all cookies transmitted with
        the request."""
        wsgi_combined_cookie = ";".join(self.headers.getlist("Cookie"))
        kwargs: dict[str, t.Any] = {}

        if self.dict_storage_class is not None:
            import warnings

            warnings.warn(
                "Setting 'Request.dict_storage_class' is deprecated and will be"
                " removed in Werkzeug 3.3. It will always be 'ImmutableMultiDict'.",
                DeprecationWarning,
                stacklevel=2,
            )
            kwargs["cls"] = self.dict_storage_class

        return parse_cookie(wsgi_combined_cookie, **kwargs)

    # Common Descriptors

    content_type = header_property[str | None](
        "Content-Type",
        read_only=True,
        doc="""The ``Content-Type`` header. The type of data in the body, with
        optional parameters for additional detail.

        A ``str``, or ``None`` if not set.

        :attr:`mimetype` and :attr:`mimetype_params` allow working with the two
        parts of the value separately.
        """,
    )

    @cached_property
    def content_length(self) -> int | None:
        """The ``Content-Length`` header. The size of the body in bytes.

        An ``int``, or ``None`` if not set.
        """
        return get_content_length(
            http_content_length=self.headers.get("Content-Length"),
            http_transfer_encoding=self.headers.get("Transfer-Encoding"),
        )

    content_encoding = header_property[str | None](
        "Content-Encoding",
        read_only=True,
        doc="""The ``Content-Encoding`` header. An additional encoding applied
        to the body beyond the ``Content-Type``.

        A ``str``, or ``None`` if not set.

        .. versionadded:: 0.9
        """,
    )

    @cached_property
    def content_md5(self) -> str | None:
        """The ``Content-MD5`` header. An MD5 digest of the body.

        A ``str``, or ``None`` if not set.

        .. deprecated:: 3.2
            The header has not been used for a long time. Will be removed
            in Werkzeug 3.3.

        .. versionadded:: 0.9
        """
        import warnings

        warnings.warn(
            "The 'content_md5' attribute is deprecated and will be removed in"
            " Werkzeug 3.3. The header has not been used for a long time.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.headers.get("Content-MD5")

    referrer = header_property[str | None](
        "Referer",
        read_only=True,
        doc="""The ``Referer`` [sic] header. The URL the client made the request
        from.

        A ``str``, or ``None`` if not set.
        """,
    )

    date = header_property[datetime | None](
        "Date",
        load_func=parse_date,
        read_only=True,
        doc="""The ``Date`` header. When the client generated the request.

        A :class:`~datetime.datetime`, or ``None`` if not set.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    max_forwards = header_property[int | None](
        "Max-Forwards",
        load_func=int,
        read_only=True,
        doc="""The ``Max-Forwards`` header. How many times to forward the
        request for ``TRACE`` or ``OPTIONS`` methods.

        An ``int``, or ``None`` if not set.
        """,
    )

    _parsed_content_type: tuple[str, dict[str, str]] | None = None

    def _parse_content_type(self) -> None:
        if self._parsed_content_type is None:
            self._parsed_content_type = parse_options_header(self.content_type)

    @cached_property
    def mimetype(self) -> str:
        """The value from :attr:`content_type`, lowercase. For example,
        ``text/HTML; charset=utf-8`` becomes ``text/html``.

        Unlike :attr:`.Response.mimetype`, this will be ``""`` if not set, and
        will be lowercase rather than the exact value.
        """
        self._parse_content_type()
        # Unlike content_type, this will be "" if the header isn't present,
        # instead of None. Checking ==/startswith/endswith is common for this,
        # so it's more convenient than None and essentially as accurate.
        return self._parsed_content_type[0].lower()  # type: ignore[index]

    @cached_property
    def mimetype_params(self) -> cabc.Mapping[str, str]:
        """The parameters from :attr:`content_type``. For example,
        ``text/html; charset=utf-8`` becomes ``{"charset": "utf-8"}``.
        """
        self._parse_content_type()
        return self._parsed_content_type[1]  # type: ignore[index]

    @cached_property
    def pragma(self) -> HeaderSet:
        """The ``Pragma`` header.

        A :class:`.HeaderSet`, empty if not set.

        .. deprecated:: 3.2
            Use ``cache_control`` instead. Will be removed in Werkzeug 3.3.
        """
        import warnings

        warnings.warn(
            "The 'pragma' attribute is deprecated and will be removed in"
            " Werkzeug 3.3. Use 'cache_control' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return HeaderSet.from_header(self.headers.get("Pragma"))

    # Accept

    accept_mimetypes = header_property[MIMEAccept](
        "Accept",
        load_func=MIMEAccept.from_header,
        read_only=True,
        doc="""The ``Accept`` header. The client's preferences for the content
        type of the response body.

        A :class:`.MIMEAccept`, empty if not set.
        """,
    )

    @cached_property
    def accept_charsets(self) -> Accept:
        """The ``Accept-Charset`` header. The client's preferences for the text
        encoding of the response body.

        An :class:`.Accept`, empty if not set.

        .. deprecated:: 3.2
            The header has not been used for a long time. Clients do not send
            it. Assume UTF-8. Will be removed in Werkzeug 3.3.
        """
        import warnings

        from ..datastructures.accept import _CharsetAccept

        warnings.warn(
            "The 'accept_charsets' attribute is deprecated and will be removed"
            " in Werkzeug 3.3. The header is not sent by browsers, and UTF-8 is"
            " assumed.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _CharsetAccept.from_header(self.headers.get("Accept-Charset"))

    accept_encodings = header_property[Accept](
        "Accept-Encoding",
        load_func=Accept.from_header,
        read_only=True,
        doc="""The ``Accept-Encoding`` header. The client's preferences for a
        further encoding applied to the response body beyond its content type.

        An :class:`.Accept`, empty if not set.
        """,
    )

    accept_languages = header_property[LanguageAccept](
        "Accept-Language",
        load_func=LanguageAccept.from_header,
        read_only=True,
        doc="""The ``Accept-Language`` header. The client's preferences for the
        natural language of the response body.

        A :class:`.LanguageAccept`, empty if not set.

        .. versionchanged 0.5
            Returns ``LanguageAccept`` instead of ``Accept``.
        """,
    )

    # ETag

    cache_control = header_property[RequestCacheControl](
        "Cache-Control",
        load_func=RequestCacheControl.from_header,
        read_only=True,
        doc="""The ``Cache-Control`` header. Controls how the application should
        cache the request.

        A :class:`.RequestCacheControl`, empty if not set.
        """,
    )

    if_match = header_property[ETagSet](
        "If-Match",
        load_func=ETagSet.from_header,
        read_only=True,
        doc="""The ``If-Match`` header. If the response's ETag is present in
        this set, it returns ``412`` instead.

        An :class:`.ETags`, empty if not set.
        """,
    )

    if_none_match = header_property[ETagSet](
        "If-None-Match",
        load_func=ETagSet.from_header,
        read_only=True,
        doc="""The ``If-None-Match`` header. If the response's ETag is present
        in this set, it returns ``304`` for ``GET`` requests, or ``412`` for
        other requests.

        An :class:`.ETags`, empty if not set.
        """,
    )

    if_modified_since = header_property[datetime | None](
        "If-Modified-Since",
        load_func=parse_date,
        read_only=True,
        doc="""The ``If-Modified-Since`` header. If the response's modification
        time is not more recent than this, it returns ``304`` instead.

        A :class:`~datetime.datetime`, or ``None`` if not set.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    if_unmodified_since = header_property[datetime | None](
        "If-Unmodified-Since",
        load_func=parse_date,
        read_only=True,
        doc="""The ``If-Unmodified-Since`` header. If the response's
        modification time is more recent than this, it returns ``412`` instead.

        A :class:`~datetime.datetime`, or ``None`` if not set.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    if_range = header_property[IfRange](
        "If-Range",
        load_func=IfRange.from_header,
        read_only=True,
        doc="""The ``If-Range`` header. If the response does not satisfy the
        condition, it ignores the ``Range`` header.

        An :class:`.IfRange`, empty if not set.

        .. versionchanged:: 3.2
            A weak ETag is discarded.

        .. versionchanged:: 2.0
            ``IfRange.date`` is timezone-aware.

        .. versionadded:: 0.7
        """,
    )

    range = header_property[Range | None](
        "Range",
        load_func=Range.from_header,
        read_only=True,
        doc="""The ``Range`` header. Partial ranges to return instead of the
        full representation.

        A :class:`.Range`, or ``None`` if not set.

        .. versionadded:: 0.7
        """,
    )

    # User Agent

    @cached_property
    def user_agent(self) -> str | None:
        """The ``User-Agent`` header. Identifies the client application to some
        degree. There are libraries that can parse this value, but it is
        generally a bad idea to change the response based on it.

        A ``str``, or ``None`` if not set.

        .. versionchanged:: 3.2
            This is a string. ``UserAgent`` and ``user_agent_class`` are
            deprecated. Parse this directly if needed.

        .. versionchanged:: 2.1
            The built-in parser was removed. Set ``user_agent_class`` to a ``UserAgent``
            subclass to parse data from the string.
        """
        value = self.headers.get("User-Agent", "")

        if self.user_agent_class is not None:
            import warnings

            warnings.warn(
                "Setting 'Request.user_agent_class' is deprecated and will be"
                " removed in Werkzeug 3.3. 'user_agent' is a string and can be"
                " parsed directly if needed.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.user_agent_class(value)

        return _UserAgent(value)

    # Authorization

    authorization = header_property[Authorization | None](
        "Authorization",
        load_func=Authorization.from_header,
        read_only=True,
        doc="""The ``Authorization`` header. Credentials used when accessing a
        protected part of the application.

        An :class:`.Authorization`, or ``None`` if not set.

        .. versionchanged:: 2.3
            The ``Authorization`` class is no longer a ``dict``. The ``token``
            attribute was added for auth schemes that use a token instead of
            parameters.
        """,
    )

    # CORS

    origin = header_property[str | None](
        "Origin",
        read_only=True,
        doc="""The ``Origin`` header. The scheme, hostname, and port of the
        location the client made the request from.

        A ``str``, or ``None`` if not set.

        Set :attr:`.Response.access_control_allow_origin` to indicate that this
        origin is allowed.
        """,
    )

    access_control_request_headers = header_property[HeaderSet](
        "Access-Control-Request-Headers",
        load_func=HeaderSet.from_header,
        read_only=True,
        doc="""The ``Access-Control-Request-Headers`` header. Sent in a
        preflight request to indicate which headers will be sent in the
        cross-origin request.

        A :class:`.HeaderSet`, empty if not set.

        Set :attr:`.Response.access_control_allow_headers` to indicate which
        headers are allowed.
        """,
    )

    access_control_request_method = header_property[str | None](
        "Access-Control-Request-Method",
        read_only=True,
        doc="""The ``Access-Control-Request-Method`` header. Sent in a
        preflight request to indicate which method will be used for the
        cross-origin request.

        A ``str``, or ``None`` if not set.

        Set :attr:`.Response.access_control_allow_methods` to indicate which
        methods are allowed.
        """,
    )

    sec_fetch_site = header_property[SecFetchSite | None](
        "Sec-Fetch-Site",
        load_func=SecFetchSite,
        read_only=True,
        doc="""The ``Sec-Fetch-Site`` header. The relationship between the
        client's current URL and the origin of the requested resource.

        A member of :class:`.SecFetchSite`, or ``None`` if not set.

        .. versionadded:: 3.2
        """,
    )

    sec_fetch_mode = header_property[SecFetchMode | None](
        "Sec-Fetch-Mode",
        load_func=SecFetchMode,
        read_only=True,
        doc="""The ``Sec-Fetch-Mode`` header. Distinguishes between requests
        originating from a user navigating between HTML pages, and requests to
        load images and other resources.

        A member of :class:`.SecFetchMode`, or ``None`` if not set.

        .. versionadded:: 3.2
        """,
    )

    sec_fetch_user = header_property[bool](
        "Sec-Fetch-User",
        default=False,
        load_func=lambda value: value == "?1",
        read_only=True,
        doc="""The ``Sec-Fetch-User`` header. Whether a navigation request was
        originated by the user.

        A ``bool``, ``False`` if not set.

        .. versionadded:: 3.2
        """,
    )

    sec_fetch_dest = header_property[SecFetchDest | None](
        "Sec-Fetch-Dest",
        load_func=SecFetchDest,
        read_only=True,
        doc="""The ``Sec-Fetch-Dest`` header. How the response to the request
        is expected to be used.

        A member of :class:`.SecFetchDest`, or ``None`` if not set.

        .. versionadded:: 3.2
        """,
    )

    @property
    def is_json(self) -> bool:
        """Check if the mimetype indicates JSON data, either
        :mimetype:`application/json` or :mimetype:`application/*+json`.
        """
        mt = self.mimetype
        return (
            mt == "application/json"
            or mt.startswith("application/")
            and mt.endswith("+json")
        )
