from __future__ import annotations

import typing as t
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus

from .._header_property import make_structure_on_update
from .._header_property import structure_property
from ..datastructures import CallbackDict
from ..datastructures import ContentRange
from ..datastructures import ContentSecurityPolicy
from ..datastructures import Headers
from ..datastructures import HeaderSet
from ..datastructures import ResponseCacheControl
from ..datastructures import WWWAuthenticate
from ..http import _dump_retry_after
from ..http import _load_retry_after
from ..http import COEP
from ..http import COOP
from ..http import CORP
from ..http import dump_age
from ..http import dump_cookie
from ..http import dump_options_header
from ..http import http_date
from ..http import parse_age
from ..http import parse_date
from ..http import parse_options_header
from ..http import quote_etag
from ..http import unquote_etag
from ..utils import get_content_type
from ..utils import header_property


class Response:
    """Represents the non-IO parts of an HTTP response, specifically the
    status and headers but not the body.

    This class is not meant for general use. It should only be used when
    implementing WSGI, ASGI, or another HTTP application spec. Werkzeug
    provides a WSGI implementation at :cls:`werkzeug.wrappers.Response`.

    :param status: The status code for the response. Either an int, in
        which case the default status message is added, or a string in
        the form ``{code} {message}``, like ``404 Not Found``. Defaults
        to 200.
    :param headers: A :class:`~werkzeug.datastructures.Headers` object,
        or a list of ``(key, value)`` tuples that will be converted to a
        ``Headers`` object.
    :param mimetype: The mime type (content type without charset or
        other parameters) of the response. If the value starts with
        ``text/`` (or matches some other special cases), the charset
        will be added to create the ``content_type``.
    :param content_type: The full content type of the response.
        Overrides building the value from ``mimetype``.

    .. versionchanged:: 3.0
        The ``charset`` attribute was removed.

    .. versionadded:: 2.0
    """

    #: the default status if none is provided.
    default_status = 200

    #: the default mimetype if none is provided.
    default_mimetype: str | None = "text/plain"

    #: Warn if a cookie header exceeds this size. The default, 4093, should be
    #: safely `supported by most browsers <cookie_>`_. A cookie larger than
    #: this size will still be sent, but it may be ignored or handled
    #: incorrectly by some browsers. Set to 0 to disable this check.
    #:
    #: .. versionadded:: 0.13
    #:
    #: .. _`cookie`: http://browsercookielimits.squawky.net/
    max_cookie_size = 4093

    # A :class:`Headers` object representing the response headers.
    headers: Headers

    def __init__(
        self,
        status: int | str | HTTPStatus | None = None,
        headers: t.Mapping[str, str | t.Iterable[str]]
        | t.Iterable[tuple[str, str]]
        | None = None,
        mimetype: str | None = None,
        content_type: str | None = None,
    ) -> None:
        if isinstance(headers, Headers):
            self.headers = headers
        elif not headers:
            self.headers = Headers()
        else:
            self.headers = Headers(headers)

        if content_type is None:
            if mimetype is None and "Content-Type" not in self.headers:
                mimetype = self.default_mimetype
            if mimetype is not None:
                mimetype = get_content_type(mimetype, "utf-8")
            content_type = mimetype
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        if status is None:
            status = self.default_status
        self.status = status

    def __repr__(self) -> str:
        return f"<{type(self).__name__} [{self.status}]>"

    @property
    def status_code(self) -> int:
        """The HTTP status code as a number."""
        return self._status_code

    @status_code.setter
    def status_code(self, code: int) -> None:
        self.status = code

    @property
    def status(self) -> str:
        """The HTTP status code as a string."""
        return self._status

    @status.setter
    def status(self, value: str | int | HTTPStatus) -> None:
        self._status, self._status_code = self._clean_status(value)

    def _clean_status(self, value: str | int | HTTPStatus) -> tuple[str, int]:
        if isinstance(value, (int, HTTPStatus)):
            status_code = int(value)
        else:
            value = value.strip()

            if not value:
                raise ValueError("Empty status argument")

            code_str, sep, _ = value.partition(" ")

            try:
                status_code = int(code_str)
            except ValueError:
                # only message
                return f"0 {value}", 0

            if sep:
                # code and message
                return value, status_code

        # only code, look up message
        try:
            status = f"{status_code} {HTTPStatus(status_code).phrase}"
        except ValueError:
            status = f"{status_code} Unknown"

        return status, status_code

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: timedelta | int | None = None,
        expires: str | datetime | int | float | None = None,
        path: str | None = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str | None = None,
        partitioned: bool = False,
    ) -> None:
        """Sets a cookie.

        A warning is raised if the size of the cookie header exceeds
        :attr:`max_cookie_size`, but the header will still be set.

        :param key: the key (name) of the cookie to be set.
        :param value: the value of the cookie.
        :param max_age: should be a number of seconds, or `None` (default) if
                        the cookie should last only as long as the client's
                        browser session.
        :param expires: should be a `datetime` object or UNIX timestamp.
        :param path: limits the cookie to a given path, per default it will
                     span the whole domain.
        :param domain: if you want to set a cross-domain cookie.  For example,
                       ``domain="example.com"`` will set a cookie that is
                       readable by the domain ``www.example.com``,
                       ``foo.example.com`` etc.  Otherwise, a cookie will only
                       be readable by the domain that set it.
        :param secure: If ``True``, the cookie will only be available
            via HTTPS.
        :param httponly: Disallow JavaScript access to the cookie.
        :param samesite: Limit the scope of the cookie to only be
            attached to requests that are "same-site".
        :param partitioned: If ``True``, the cookie will be partitioned.

        .. versionchanged:: 3.1
            The ``partitioned`` parameter was added.
        """
        self.headers.add(
            "Set-Cookie",
            dump_cookie(
                key,
                value=value,
                max_age=max_age,
                expires=expires,
                path=path,
                domain=domain,
                secure=secure,
                httponly=httponly,
                max_size=self.max_cookie_size,
                samesite=samesite,
                partitioned=partitioned,
            ),
        )

    def delete_cookie(
        self,
        key: str,
        path: str | None = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str | None = None,
        partitioned: bool = False,
    ) -> None:
        """Delete a cookie.  Fails silently if key doesn't exist.

        :param key: the key (name) of the cookie to be deleted.
        :param path: if the cookie that should be deleted was limited to a
                     path, the path has to be defined here.
        :param domain: if the cookie that should be deleted was limited to a
                       domain, that domain has to be defined here.
        :param secure: If ``True``, the cookie will only be available
            via HTTPS.
        :param httponly: Disallow JavaScript access to the cookie.
        :param samesite: Limit the scope of the cookie to only be
            attached to requests that are "same-site".
        :param partitioned: If ``True``, the cookie will be partitioned.
        """
        self.set_cookie(
            key,
            expires=0,
            max_age=0,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
            partitioned=partitioned,
        )

    @property
    def is_json(self) -> bool:
        """Check if the mimetype indicates JSON data, either
        :mimetype:`application/json` or :mimetype:`application/*+json`.
        """
        mt = self.mimetype
        return mt is not None and (
            mt == "application/json"
            or mt.startswith("application/")
            and mt.endswith("+json")
        )

    # Common Descriptors

    @property
    def mimetype(self) -> str | None:
        """The value from :attr:`content_type`. For example,
        ``text/html; charset=utf-8`` becomes``text/html``.

        Unlike :attr:`.Request.mimetype`, this will be ``None`` if not set, and
        will be the exact value rather than lowercase.

        Setting this will clear :attr:`mimetype_params`. Set to ``None`` or use
        ``del`` to unset the header.
        """
        if ct := self.headers.get("Content-Type"):
            return ct.partition(";")[0].strip()

        return None

    @mimetype.setter
    def mimetype(self, value: str | None) -> None:
        if not value:
            del self.headers["Content-Type"]
        else:
            self.headers["Content-Type"] = get_content_type(value, "utf-8")

    @mimetype.deleter
    def mimetype(self) -> None:
        del self.headers["Content-Type"]

    @property
    def mimetype_params(self) -> dict[str, str]:
        """The parameters from :attr:`content_type``. For example,
        ``text/html; charset=utf-8`` becomes ``{"charset": "utf-8"}``.

        Modifying the dict will update the header if it is set.

        .. versionchanged:: 3.2
            When the header is not set, modifying does nothing instead of
            producing an invalid value.

        .. versionadded:: 0.5
        """

        def on_update(value: CallbackDict[str, str]) -> None:
            if not (mt := self.mimetype):
                return

            self.headers["Content-Type"] = dump_options_header(mt, value)

        d = parse_options_header(self.headers.get("Content-Type"))[1]
        return CallbackDict(d, on_update)

    location = header_property[str | None](
        "Location",
        doc="""The ``Location`` header. The URL the client should redirect to
        after this response. Used with ``3xx`` redirects and ``201 Created``.

        A ``str``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.
        """,
    )
    age = header_property(
        "Age",
        None,
        parse_age,
        dump_age,  # type: ignore
        doc="""The Age response-header field conveys the sender's
        estimate of the amount of time since the response (or its
        revalidation) was generated at the origin server.

        Age values are non-negative decimal integers, representing time
        in seconds.""",
    )
    content_type = header_property[str](
        "Content-Type",
        doc="""The Content-Type entity-header field indicates the media
        type of the entity-body sent to the recipient or, in the case of
        the HEAD method, the media type that would have been sent had
        the request been a GET.""",
    )
    content_length = header_property(
        "Content-Length",
        None,
        int,
        str,
        doc="""The Content-Length entity-header field indicates the size
        of the entity-body, in decimal number of OCTETs, sent to the
        recipient or, in the case of the HEAD method, the size of the
        entity-body that would have been sent had the request been a
        GET.""",
    )
    content_location = header_property[str](
        "Content-Location",
        doc="""The Content-Location entity-header field MAY be used to
        supply the resource location for the entity enclosed in the
        message when that entity is accessible from a location separate
        from the requested resource's URI.""",
    )
    content_encoding = header_property[str](
        "Content-Encoding",
        doc="""The Content-Encoding entity-header field is used as a
        modifier to the media-type. When present, its value indicates
        what additional content codings have been applied to the
        entity-body, and thus what decoding mechanisms must be applied
        in order to obtain the media-type referenced by the Content-Type
        header field.""",
    )

    @property
    def content_md5(self) -> str | None:
        """The ``Content-MD5`` header, an MD5 digest of the response body.

        .. deprecated:: 3.2
            The header has not been used for a long time. Will be removed
            in Werkzeug 3.3.
        """
        import warnings

        warnings.warn(
            "The 'content_md5' attribute is deprecated and will be removed in"
            " Werkzeug 3.3. The header has not been used for a long time.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.headers.get("Content-MD5")

    @content_md5.setter
    def content_md5(self, value: str | None) -> None:
        import warnings

        warnings.warn(
            "The 'content_md5' attribute is deprecated and will be removed in"
            " Werkzeug 3.3. The header has not been used for a long time.",
            DeprecationWarning,
            stacklevel=2,
        )

        if value is None:
            del self.headers["Content-MD5"]
        else:
            self.headers["Content-MD5"] = value

    @content_md5.deleter
    def content_md5(self) -> None:
        import warnings

        warnings.warn(
            "The 'content_md5' attribute is deprecated and will be removed in"
            " Werkzeug 3.3. The header has not been used for a long time.",
            DeprecationWarning,
            stacklevel=2,
        )
        del self.headers["Content-MD5"]

    date = header_property(
        "Date",
        None,
        parse_date,
        http_date,
        doc="""The Date general-header field represents the date and
        time at which the message was originated, having the same
        semantics as orig-date in RFC 822.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )
    expires = header_property(
        "Expires",
        None,
        parse_date,
        http_date,
        doc="""The Expires entity-header field gives the date/time after
        which the response is considered stale. A stale cache entry may
        not normally be returned by a cache.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )
    last_modified = header_property(
        "Last-Modified",
        None,
        parse_date,
        http_date,
        doc="""The Last-Modified entity-header field indicates the date
        and time at which the origin server believes the variant was
        last modified.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    retry_after = header_property[datetime | None](
        "Retry-After",
        load_func=_load_retry_after,
        dump_func=_dump_retry_after,  # type: ignore[arg-type]
        doc="""The ``Retry-After`` header. The client should wait until after this
        time to make a follow-up request.

        A :class:`~datetime.datetime`, or ``None`` if not set. Set to a
        ``datetime`` to send a date string, or an ``int`` to send a number of
        seconds. Set to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    vary = structure_property[HeaderSet](
        "Vary",
        HeaderSet,
        doc="""The ``Vary`` header. The set of request headers that affected the
        response. Caches will not send a cached response if another request
        doesn't have the same header values.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.
        """,
        deprecate_str=True,
    )

    content_language = structure_property[HeaderSet](
        "Content-Language",
        HeaderSet,
        doc="""The ``Content-Language`` header. The natural languages of the
        response body.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.

        :attr:`.Request.accept_languages` can be used to check the client's
        preferences.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.
        """,
        deprecate_str=True,
    )

    allow = structure_property[HeaderSet](
        "Allow",
        HeaderSet,
        doc="""The ``Allow`` header. The set of methods supported for the URL.
        Sent for ``OPTIONS`` and ``405`` responses.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.
        """,
        deprecate_str=True,
    )

    # ETag

    cache_control = structure_property[ResponseCacheControl](
        "Cache-Control",
        ResponseCacheControl,
        doc="""The ``Cache-Control`` header. Directives that control how the
        client should cache the response.

        A :class:`.ResponseCacheControl`, or empty if the header is not set.
        Modifying the instance updates the header, but it is more efficient
        to set a new instance. Set to ``None`` or use ``del`` to unset the
        header.

        .. versionchanged:: 3.2
            Can be set to an instance or ``None``, and can use ``del``.
        """,
    )

    def set_etag(self, etag: str, weak: bool = False) -> None:
        """Set the etag, and override the old one if there was one."""
        self.headers["ETag"] = quote_etag(etag, weak)

    def get_etag(self) -> tuple[str, bool] | tuple[None, None]:
        """Return a tuple in the form ``(etag, is_weak)``.  If there is no
        ETag the return value is ``(None, None)``.
        """
        return unquote_etag(self.headers.get("ETag"))

    accept_ranges = header_property[str](
        "Accept-Ranges",
        doc="""The `Accept-Ranges` header. Even though the name would
        indicate that multiple values are supported, it must be one
        string token only.

        The values ``'bytes'`` and ``'none'`` are common.

        .. versionadded:: 0.7""",
    )

    content_range = structure_property[ContentRange](
        "Content-Range",
        ContentRange,
        doc="""The ``Content-Range`` header. The partial range being returned in
        response to a ``Range`` request.

        A :class:`.ContentRange`, empty if not set. Modifying the instance
        updates the header, but it is more effiecient to set a new instance. Set
        to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.

        .. versionadded:: 0.7
        """,
        deprecate_str=True,
    )

    # Authorization

    www_authenticate = structure_property[WWWAuthenticate](
        "WWW-Authenticate",
        WWWAuthenticate,
        doc="""The ``WWW-Authenticate`` header. The authentication method needed
        to access this resource. Sent with ``401`` errors.

        A :class:`.WWWAuthenticate`, empty if not set. Modifying the instance
        updates the header, but it is more efficient to set a new instance. Set
        to ``None`` or use ``del`` to unset the header.

        Set to a ``list[WWWAuthenticate]`` to set multiple values. Modifying the
        values in the list does not update the header. Accessing will only
        return the first value.

        .. versionchanged:: 3.2
            :attr:`WWWAuthenticate.type` is empty if the header is not set.
            Setting to a ``str`` is deprecated and will be removed in Werkzeug
            3.3. Set ``headers`` directly instead.

        .. versionchanged:: 2.3
            Can be assigned to set the header. A list will set multiple header
            values. Set ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 2.3
            :class:`WWWAuthenticate` is no longer a ``dict``. The ``token``
            attribute was added for auth challenges that use a token instead of
            parameters.
        """,
        deprecate_str=True,
    )

    @www_authenticate.register_setter
    def _set_www_authenticate(
        self, value: WWWAuthenticate | list[WWWAuthenticate]
    ) -> None:
        if isinstance(value, list):
            self.headers.setlist("WWW-Authenticate", (v.to_header() for v in value))
        else:
            self.headers["WWW-Authenticate"] = value.to_header()
            value._on_update = make_structure_on_update(
                self, "WWW-Authenticate", WWWAuthenticate
            )

    # CSP

    content_security_policy = structure_property[ContentSecurityPolicy](
        "Content-Security-Policy",
        ContentSecurityPolicy,
        doc="""The ``Content-Security-Policy`` header. Controls how the client
        loads resources for the returned page.

        A :class:`.ContentSecurityPolicy`, empty if not set. Modifying the
        instance updates the header, but it it more efficient to set a new
        instance. Set to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.
        """,
        deprecate_str=True,
    )

    content_security_policy_report_only = structure_property[ContentSecurityPolicy](
        "Content-Security-Policy-Report-Only",
        ContentSecurityPolicy,
        doc="""The ``Content-Security-Policy-Report-Only`` header. Controls how
        the client loads resources for the returned page. Violations are only
        reported and do not cause the client to stop.

        A :class:`.ContentSecurityPolicy`, empty if not set. Modifying the
        instance updates the header, but it it more efficient to set a new
        instance. Set to ``None`` or use ``del`` to unset the header.

        .. versionchanged:: 3.2
            Setting to a ``str`` is deprecated and will be removed in Werkzeug 3.3.
            Set ``headers`` directly instead.
        """,
        deprecate_str=True,
    )

    # CORS

    @property
    def access_control_allow_credentials(self) -> bool:
        """Whether credentials can be shared by the browser to
        JavaScript code. As part of the preflight request it indicates
        whether credentials can be used on the cross origin request.
        """
        return "Access-Control-Allow-Credentials" in self.headers

    @access_control_allow_credentials.setter
    def access_control_allow_credentials(self, value: bool | None) -> None:
        if value is True:
            self.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            self.headers.pop("Access-Control-Allow-Credentials", None)

    access_control_allow_headers = structure_property[HeaderSet](
        "Access-Control-Allow-Headers",
        HeaderSet,
        doc="""The ``Access-Control-Allow-Headers`` header. Which headers are
        allowed in a cross-origin request.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.
        """,
    )

    access_control_allow_methods = structure_property[HeaderSet](
        "Access-Control-Allow-Methods",
        HeaderSet,
        doc="""The ``Access-Control-Allow-Methods`` header. Which methods are
        allowed in a cross-origin request.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.
        """,
    )

    access_control_allow_origin = header_property[str](
        "Access-Control-Allow-Origin",
        doc="The origin or '*' for any origin that may make cross origin requests.",
    )

    access_control_expose_headers = structure_property[HeaderSet](
        "Access-Control-Expose-Headers",
        HeaderSet,
        doc="""The ``Access-Control-Allow-Origin`` header. Which response
        headers are allowed to be accessed by scripts.

        A :class:`.HeaderSet`, empty if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to a
        ``HeaderSet``, or a basic collection like ``set``, ``list``, or
        ``tuple``. Set to ``None`` or use ``del`` to unset the header.
        """,
    )

    access_control_max_age = header_property(
        "Access-Control-Max-Age",
        load_func=int,
        dump_func=str,
        doc="The maximum age in seconds the access control settings can be cached for.",
    )

    cross_origin_opener_policy = header_property[COOP](
        "Cross-Origin-Opener-Policy",
        load_func=COOP,
        dump_func=lambda value: value.value,
        default=COOP.UNSAFE_NONE,
        doc="""Allows control over sharing of browsing context group with cross-origin
        documents.

        Values are members of the :class:`.COOP` enum.

        .. versionadded:: 2.0
        """,
    )

    cross_origin_embedder_policy = header_property[COEP](
        "Cross-Origin-Embedder-Policy",
        load_func=COEP,
        dump_func=lambda value: value.value,
        default=COEP.UNSAFE_NONE,
        doc="""Prevents a document from loading any cross-origin resources that do not
        explicitly grant the document permission.

        Values are members of the :class:`.COEP` enum.

        .. versionadded:: 2.0
        """,
    )

    cross_origin_resource_policy = header_property[CORP](
        "Cross-Origin-Resource-Policy",
        load_func=CORP,
        dump_func=lambda value: value.value,
        doc="""specifies the policy for what sites/origins should be allowed to load
        this resource.

        Values are members of the :class:`.CORP` enum.

        .. versionadded:: 3.2
        """,
    )
