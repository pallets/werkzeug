from __future__ import annotations

import typing as t
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus

from .._header_property import header_property
from .._header_property import make_structure_on_update
from .._header_property import structure_property
from ..datastructures.auth import WWWAuthenticate
from ..datastructures.cache_control import ResponseCacheControl
from ..datastructures.csp import ContentSecurityPolicy
from ..datastructures.etag import ETag
from ..datastructures.headers import Headers
from ..datastructures.range import ContentRange
from ..datastructures.set import HeaderSet
from ..datastructures.structures import CallbackDict
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
from ..utils import get_content_type


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

    age = header_property[timedelta | None](
        "Age",
        load_func=parse_age,
        dump_func=dump_age,
        doc="""The ``Age`` header. The time in seconds since the response data
        was generated. Implies that the data was returned by a cache rather than
        generated or validated by its origin.

        A :class:`~datetime.timedelta`, or ``None`` if not set. Set to a
        ``timedelta`` or ``int`` number of seconds. Set to ``None`` or use
        ``del`` to unset the header.
        """,
    )

    content_type = header_property[str | None](
        "Content-Type",
        doc="""The ``Content-Type`` header. The type of data in the response
        body, with optional parameters for additional detail.

        :attr:`mimetype` and :attr:`mimetype_params` allow working with the two
        parts of the value separately.

        :attr:`.Request.accept_mimetypes` can be used to check the client's
        preferences.
        """,
    )

    content_length = header_property[int | None](
        "Content-Length",
        load_func=int,
        doc="""The ``Content-Length`` header. The size of the body in bytes.

        An ``int``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.
        """,
    )

    content_location = header_property[str | None](
        "Content-Location",
        doc="""The ``Content-Location`` header. A more specific URL for the same
        negotiated resource.

        A ``str``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.
        """,
    )

    content_encoding = header_property[str | None](
        "Content-Encoding",
        doc="""The ``Content-Encoding`` header. An additional encoding applied
        to the body beyond the ``Content-Type``.

        A ``str``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.

        :attr:`.Request.accept_encodings`` can be used to check the client's
        preferences.
        """,
    )

    @property
    def content_md5(self) -> str | None:
        """The ``Content-MD5`` header. An MD5 digest of the response body.

        A ``str``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.

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

    date = header_property[datetime | None](
        "Date",
        load_func=parse_date,
        dump_func=http_date,
        doc="""The ``Date`` header. When the application generated the response.

        A :class:`~datetime.datetime`, or ``None`` if not set. Set to a
        ``datetime`` or an ``int``/``float`` timestamp. Set to ``None`` or use
        ``del`` to unset the header.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    expires = header_property[datetime | None](
        "Expires",
        load_func=parse_date,
        dump_func=http_date,
        doc="""The ``Expires`` header. The time after which a cache of this
        response is considered stale.

        :attr:`.CacheControl.max_age`` is preferred over this.

        A :class:`~datetime.datetime`, or ``None`` if not set. Set to a
        ``datetime`` or an ``int``/``float`` timestamp. Set to ``None`` or use
        ``del`` to unset the header.

        .. versionchanged:: 2.0
            The datetime object is timezone-aware.
        """,
    )

    last_modified = header_property[datetime | None](
        "Last-Modified",
        load_func=parse_date,
        dump_func=http_date,
        doc="""The ``Last-Modified`` header. When the resource was last
        modified. The client uses this to make conditional requests with
        ``If-Modified-Since``, ``If-Unmodified-Since``, and ``If-Range``.

        A :class:`~datetime.datetime`, or ``None`` if not set. Set to a
        ``datetime`` or an ``int``/``float`` timestamp. Set to ``None`` or use
        ``del`` to unset the header.

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

    etag = structure_property[ETag](
        "ETag",
        ETag,
        doc="""The ``ETag`` header. A hash that identifies the state of the
        resource for use in conditional requests.

        A :class:`.ETag`, or ``None`` if not set. Modifying the instance updates
        the header, but it is more efficient to set a new instance. Set to an
        ``ETag``, or a ``(value, weak)`` tuple, or a ``str`` meaning
        ``(value, False)``. Set to ``None`` or use ``del`` to unset the header.

        .. versionadded:: 3.2
        """,
    )

    @etag.register_setter
    def _set_etag(self, value: ETag | tuple[str, bool] | str) -> None:
        if isinstance(value, str):
            value = ETag(value)
        elif isinstance(value, tuple):
            value = ETag(*value)

        self.headers["ETag"] = value.to_header()
        value._on_update = make_structure_on_update(self, "ETag", ETag)

    def set_etag(self, etag: str, weak: bool = False) -> None:
        """Set the ``ETag`` header.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``etag`` instead.
        """
        import warnings

        warnings.warn(
            "'set_etag' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'etag' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.etag = ETag(etag, weak)

    def get_etag(self) -> tuple[str, bool] | tuple[None, None]:
        """The ``ETag`` header as ``(value, weak)``, or ``(None, None)`` if not
        set.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``etag`` instead.
        """
        import warnings

        warnings.warn(
            "'get_etag' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'etag' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if (result := self.etag) is None:
            return None, None

        return result.value, result.weak

    accept_ranges = header_property[str | None](
        "Accept-Ranges",
        doc="""The ``Accept-Ranges`` header. Indicates that a request could
        include the ``Range`` header. The value is the unit that will be
        accepted, a single value despite the plural name. The only specified
        value is ``bytes``.

        A ``str``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.

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

    access_control_allow_credentials = header_property[bool](
        "Access-Control-Allow-Credentials",
        default=False,
        load_func=lambda value: value == "true",
        dump_func=lambda value: "true" if value is True else None,
        doc="""The ``Access-Control-Allow-Credentials`` header. Whether
        credentials are allowed in a cross-origin request.

        A ``bool``, ``False`` if not set. Set to ``False`` or use ``del`` to
        unset the header.
        """,
    )

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

    access_control_allow_origin = header_property[str | None](
        "Access-Control-Allow-Origin",
        doc="""The ``Access-Control-Allow-Origin`` header. Whether the origin of
        the request is allowed to make cross-origin requests.

        A ``str``, or ``None`` if not set. Set to ``*`` to allow any origin,
        or set to the request's ``Origin`` to allow that origin. Set to ``None``
        or use ``del`` to unset the header.
        """,
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

    access_control_max_age = header_property[int | None](
        "Access-Control-Max-Age",
        load_func=int,
        doc="""The ``Access-Control-Max-Age`` header. How long in seconds the
        access control headers in a response are valid.

        An ``int``, or ``None`` if not set. Set to ``None`` or use ``del`` to
        unset the header.
        """,
    )

    cross_origin_opener_policy = header_property[COOP](
        "Cross-Origin-Opener-Policy",
        default=COOP.UNSAFE_NONE,
        load_func=COOP,
        dump_func=lambda value: value.value,
        doc="""The ``Cross-Origin-Opener-Policy`` header. How additional windows
        opened from the page are allowed to communicate with the page.

        A member of :class:`.COOP`, ``UNSAFE_NONE`` if not set. Set to ``None``
        or use ``del`` to unset the header.

        .. versionadded:: 2.0
        """,
    )

    cross_origin_embedder_policy = header_property[COEP](
        "Cross-Origin-Embedder-Policy",
        default=COEP.UNSAFE_NONE,
        load_func=COEP,
        dump_func=lambda value: value.value,
        doc="""The ``Cross-Origin-Embedder-Policy`` header. How cross-origin
        resources are allowed to be loaded in ``no-cors`` mode.

        A member of :class:`.COEP`, ``UNSAFE_NONE`` if not set. Set to ``None``
        or use ``del`` to unset the header.

        .. versionadded:: 2.0
        """,
    )

    cross_origin_resource_policy = header_property[CORP | None](
        "Cross-Origin-Resource-Policy",
        load_func=CORP,
        dump_func=lambda value: value.value,  # type: ignore[union-attr]
        doc="""The ``Cross-Origin-Resource-Policy`` header. Whether cross-origin
        requests can load this resource.

        A member of :class:`.CORP`, or ``None`` if not set. Set to ``None`` or
        use ``del`` to unset the header.

        .. versionadded:: 3.2
        """,
    )
