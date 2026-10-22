from __future__ import annotations

import typing as t
import wsgiref.types as wt
from datetime import datetime
from http import HTTPStatus

from markupsafe import escape
from markupsafe import Markup

from ._internal import _get_environ

if t.TYPE_CHECKING:
    from .datastructures.auth import WWWAuthenticate
    from .wrappers.response import Response as WSGIResponse


class HTTPException(Exception):
    """An HTTP error status as an exception. It can be converted to an HTML
    response describing the error, and called as a WSGI application.

    All the exceptions take the following two keyword parameters to customize
    the error. Certain exceptions may take other arguments based on the headers
    they need to return.

    :param description: Override the default error page description.
    :param response: Use this response instead of generating one. This allows
        using the exception for flow control, while completely controlling the
        response.

    .. versionchanged:: 2.1
        The ``wrap`` class method was removed.
    """

    code: int = 0
    name: str = ""
    description: str = ""

    _override_get_description = False
    _override_get_body = False
    _override_get_headers = False
    _override_get_response = False

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)

        # Automatically fill in `name` from the `HTTPStatus` enum.
        if not cls.name:
            try:
                cls.name = HTTPStatus(cls.code).phrase
            except ValueError:
                pass

        # Automatically add the standard code, title, link to the top of the doc.
        # Skip special subclasses that inherit `code`.
        if "code" in cls.__dict__:
            title = f"{cls.code} {cls.name}"
            doc = (
                f"{title}\n\n{cls.description}\n\nhttps://developer.mozilla.org"
                f"/en-US/docs/Web/HTTP/Reference/Status/{cls.code}"
            )

            if not cls.__doc__:
                cls.__doc__ = doc
            elif not cls.__doc__.lstrip().startswith(title):
                cls.__doc__ = f"{doc}\n\n{cls.__doc__.lstrip()}"

        for name in ("get_description", "get_body", "get_headers", "get_response"):
            if getattr(cls, name) is not getattr(HTTPException, name):
                if name != "get_response":
                    import warnings

                    warnings.warn(
                        f"The '{name}' method is deprecated and will be removed in"
                        " Werkzeug 4.0. Override 'get_response' instead.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

                setattr(cls, f"_override_{name}", True)

    def __init__(
        self, description: str | None = None, response: WSGIResponse | None = None
    ) -> None:
        super().__init__()

        if description is not None:
            self.description = description

        self.response = response

    def get_description(
        self,
        environ: wt.WSGIEnvironment | None = None,
        scope: dict[str, t.Any] | None = None,
    ) -> str:
        """The description as an HTML paragraph. HTML characters are escaped,
        and newlines are replaced with ``<br>``.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_description' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_description()

    def _get_description(self) -> str:
        # TODO remove after deprecation
        description = escape(self.description).replace("\n", Markup("<br>"))
        return f"<p>{description}</p>"

    def get_body(self, environ: None = None, scope: None = None) -> str:
        """The HTML error page.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_body' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_body()

    def _get_body(self) -> str:
        # TODO remove after deprecation
        if self._override_get_description:
            description = self.get_description()
        else:
            description = self._get_description()

        title = f"{self.code} {escape(self.name)}"
        return (
            "<!doctype html>\n<html lang=en>\n<head>\n<meta charset=utf-8>\n"
            f"<title>{title}</title>\n</head>\n<body>\n<h1>{title}</h1>\n"
            f"{description}\n</body>\n</html>\n"
        )

    def get_headers(
        self, environ: None = None, scope: None = None
    ) -> list[tuple[str, str]]:
        """The headers to send with the response.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_headers' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return [("Content-Type", "text/html; charset=utf-8")]

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        """Get the response for this error. If :attr:`response` was given when
        creating the error, it will be returned. Otherwise, a default response
        with an HTML error page and any error-specific headers is built.

        .. versionchanged:: 3.2
            The ``environ`` and ``scope`` parameters are deprecated and will be
            removed in Werkzeug 4.0.
        """
        from .wrappers.response import Response

        if self.response is not None:
            return self.response

        if environ is not None:
            import warnings

            warnings.warn(
                "The 'environ' parameter is deprecated and will be"
                " removed in Werkzeug 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            environ = _get_environ(environ)

        if scope is not None:
            import warnings

            warnings.warn(
                "The 'scope' parameter is deprecated and will be"
                " removed in Werkzeug 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        if self._override_get_headers:
            content_type = None
            headers = self.get_headers(environ, scope)
        else:
            content_type = "text/html; charset=utf-8"
            headers = None

        if self._override_get_body:
            body = self.get_body(environ, scope)
        else:
            body = self._get_body()

        return Response(body, self.code, headers, content_type=content_type)

    def __call__(
        self, environ: wt.WSGIEnvironment, start_response: wt.StartResponse
    ) -> t.Iterable[bytes]:
        if self._override_get_response:
            response = self.get_response(environ)  # type: ignore[arg-type]
        else:
            response = self.get_response()

        return response(environ, start_response)

    def __str__(self) -> str:
        return f"{self.code} {self.name}: {self.description}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.code} {self.name}'>"


class BadRequest(HTTPException):
    code = 400
    description = "The request is invalid."


class BadRequestKeyError(BadRequest, KeyError):
    """Signals both a :exc:`.KeyError` and a :exc:`.BadRequest`. Raised for a
    missing key in :class:`.MultiDict` and :class:`.Headers`. If a client didn't
    send an expected query arg, form field, cookie, header, etc., a 400 error
    response is correct. Or it can be caught as a normal ``KeyError`` in code.
    """

    _description = BadRequest.description
    #: Show the KeyError along with the HTTP error message in the
    #: response. This should be disabled in production, but can be
    #: useful in a debug mode.
    show_exception = False

    def __init__(self, arg: object | None = None, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, **kwargs)

        if arg is None:
            KeyError.__init__(self)
        else:
            KeyError.__init__(self, arg)

    @property
    def description(self) -> str:
        if self.show_exception:
            return f"{self._description}\n{KeyError.__name__}: {KeyError.__str__(self)}"

        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value


class ClientDisconnected(BadRequest):
    """The client disconnected while processing the request. Since the
    connection is closed, this probably can't be returned as a response.

    .. versionadded:: 0.8
    """


class SecurityError(BadRequest):
    """The request is invalid in some way that may indicate a security event.

    .. versionadded:: 0.9
    """


class BadHost(BadRequest):
    """The request's ``Host`` header is invalid.

    .. versionadded:: 0.11.2
    """


class Unauthorized(HTTPException):
    """
    :param www_authenticate: Set one or more ``WWW-Authenticate`` headers to
        tell the client which authentication methods are accepted. The response
        is technically invalid if this is not given.

    .. versionchanged:: 2.0
        Serialize multiple ``www_authenticate`` items into multiple
        ``WWW-Authenticate`` headers, rather than joining them
        into a single value, for better interoperability.

    .. versionchanged:: 0.15.3
        If the ``www_authenticate`` argument is not set, the
        ``WWW-Authenticate`` header is not set.

        The ``response`` argument was restored.

    .. versionchanged:: 0.15.1
        ``description`` was moved back as the first argument, restoring
         its previous position.

    .. versionchanged:: 0.15.0
        ``www_authenticate`` was added as the first argument, ahead of
        ``description``.
    """

    code = 401
    description = "Missing or invalid authentication credentials."

    def __init__(
        self,
        description: str | None = None,
        response: WSGIResponse | None = None,
        www_authenticate: WWWAuthenticate | t.Iterable[WWWAuthenticate] | None = None,
    ) -> None:
        super().__init__(description=description, response=response)

        from .datastructures.auth import WWWAuthenticate

        if isinstance(www_authenticate, WWWAuthenticate):
            www_authenticate = (www_authenticate,)

        self.www_authenticate = www_authenticate

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        response = super().get_response()
        response.www_authenticate = self.www_authenticate
        return response


class Forbidden(HTTPException):
    code = 403
    description = "Insufficient permissions for the requested resource."


class NotFound(HTTPException):
    code = 404
    description = "The requested resource does not exist."


class MethodNotAllowed(HTTPException):
    """
    :param valid_methods: Set the ``Allow`` header to inform the client which
        methods are allowed. The response is technically invalid if this is not
        given.
    """

    code = 405
    description = "The request method is not allowed."

    def __init__(
        self,
        valid_methods: t.Iterable[str] | None = None,
        description: str | None = None,
        response: WSGIResponse | None = None,
    ) -> None:
        super().__init__(description=description, response=response)

        if valid_methods is None:
            valid_methods = ()

        self.valid_methods: t.Iterable[str] = valid_methods

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        response = super().get_response()
        response.allow = self.valid_methods
        return response


class NotAcceptable(HTTPException):
    code = 406
    description = "The client's indicated preferences could not be matched."


class RequestTimeout(HTTPException):
    code = 408
    description = "A complete request was not received in time."


class Conflict(HTTPException):
    """
    .. versionadded:: 0.7
    """

    code = 409
    description = "There is a conflict with the current state of the resource."


class Gone(HTTPException):
    code = 410
    description = "The requested resource no longer exists."


class LengthRequired(HTTPException):
    code = 411
    description = "The request must specify its length."


class PreconditionFailed(HTTPException):
    code = 412
    description = (
        "The requested conditions do not match the current state of the resource."
    )


class RequestEntityTooLarge(HTTPException):
    code = 413
    description = "The data is larger than what the server allows."


class RequestURITooLarge(HTTPException):
    code = 414
    description = "The URL is longer than what the server allows."


class UnsupportedMediaType(HTTPException):
    code = 415
    description = "The data format is not supported."


class RequestedRangeNotSatisfiable(HTTPException):
    """
    .. versionadded:: 0.7
    """

    code = 416
    description = "The requested range cannot be provided."

    def __init__(
        self,
        length: int | None = None,
        units: str = "bytes",
        description: str | None = None,
        response: WSGIResponse | None = None,
    ) -> None:
        from .datastructures.range import ContentRange

        super().__init__(description=description, response=response)
        self.content_range = ContentRange(units=units, length=length)

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        response = super().get_response()
        response.content_range = self.content_range
        return response


class ExpectationFailed(HTTPException):
    """
    .. versionadded:: 0.7
    """

    code = 417
    description = "The requested expectations could not be met."


class ImATeapot(HTTPException):
    """
    .. versionadded:: 0.7
    """

    code = 418
    description = "The server is a teapot, not a coffee machine."


class MisdirectedRequest(HTTPException):
    """
    .. versionadded:: 3.1
    """

    code = 421
    description = (
        "The server is not able to produce a response, the request should be"
        " directed to another server."
    )


class UnprocessableEntity(HTTPException):
    code = 422
    description = "The data format is supported, but the data is invalid."


class Locked(HTTPException):
    code = 423
    description = "The resource is currently locked and can't be accessed."


class FailedDependency(HTTPException):
    code = 424
    description = "The current action depends on another action that failed."


class PreconditionRequired(HTTPException):
    code = 428
    description = "The request must contain conditions."


class _RetryAfter(HTTPException):
    """Adds an optional ``retry_after`` parameter which will set the
    ``Retry-After`` header.
    """

    def __init__(
        self,
        description: str | None = None,
        response: WSGIResponse | None = None,
        retry_after: datetime | int | None = None,
    ) -> None:
        super().__init__(description, response)
        self.retry_after = retry_after

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        response = super().get_response()
        response.retry_after = self.retry_after
        return response


class TooManyRequests(_RetryAfter):
    """
    :param retry_after: Set the ``Retry-After`` header. An ``int`` number of
        seconds from now, or a specific ``datetime``.

    .. versionchanged:: 1.0
        The ``retry_after`` parameter was added.
    """

    code = 429
    description = "This client has made too many requests too quickly."


class RequestHeaderFieldsTooLarge(HTTPException):
    code = 431
    description = "The headers are larger than what the server allows."


class UnavailableForLegalReasons(HTTPException):
    code = 451
    description = "The resource is not available for legal reasons."


class InternalServerError(HTTPException):
    """
    :param original_exception: The exception that caused this 500 error.

    .. versionchanged:: 1.0.0
        The ``original_exception`` parameter and attribute was added.
    """

    code = 500
    description = "The server encountered an unexpected error."

    def __init__(
        self,
        description: str | None = None,
        response: WSGIResponse | None = None,
        original_exception: BaseException | None = None,
    ) -> None:
        super().__init__(description=description, response=response)

        self.original_exception = original_exception
        """The exception that caused this 500 error. Can be used to provide
        context when handling unexpected errors.
        """


class NotImplemented(HTTPException):
    code = 501
    description = "The server does not support the requested action."


class BadGateway(HTTPException):
    code = 502
    description = "The proxy received an invalid response from the upstream server."


class ServiceUnavailable(_RetryAfter):
    """
    :param retry_after: Set the ``Retry-After`` header. An ``int`` number of
        seconds from now, or a specific ``datetime``.

    .. versionchanged:: 1.0
        The ``retry_after`` parameter was added.
    """

    code = 503
    description = "The server is not currently available to handle the request."


class GatewayTimeout(HTTPException):
    code = 504
    description = (
        "The proxy did not receive a complete response from the upstream server"
        " in time."
    )


class HTTPVersionNotSupported(HTTPException):
    code = 505
    description = "The server does not support the HTTP version used by the client."


default_exceptions: dict[int, type[HTTPException]] = {}


def _find_exceptions() -> None:
    for obj in globals().values():
        if obj is HTTPException:
            continue

        try:
            is_http_exception = issubclass(obj, HTTPException)
        except TypeError:
            is_http_exception = False

        if not is_http_exception or not obj.code:
            continue

        if (old_obj := default_exceptions.get(obj.code, None)) is not None:
            if issubclass(obj, old_obj):
                # special subclass, ignore
                continue

            # accidentally redefined a status code
            raise TypeError(f"{obj} redefines {obj.code} from {old_obj}")

        default_exceptions[obj.code] = obj


_find_exceptions()
del _find_exceptions


class Aborter:
    """Map status codes to HTTP exceptions. Used by :func:`abort`.

    :param mapping: The map of HTTP status codes to HTTP exceptions. Defaults to
        Werkzeug's built-in exceptions.
    :param extra: Extend ``mapping`` with these additional items. Use to
        override or extend the default exceptions.
    """

    def __init__(
        self,
        mapping: dict[int, type[HTTPException]] | None = None,
        extra: dict[int, type[HTTPException]] | None = None,
    ) -> None:
        if mapping is None:
            mapping = default_exceptions

        self.mapping = dict(mapping)

        if extra is not None:
            self.mapping.update(extra)

    def __call__(
        self, status: int | WSGIResponse, *args: t.Any, **kwargs: t.Any
    ) -> t.NoReturn:
        """Raise an :exc:`.HTTPException` for the given status or response.

        :param status: An HTTP error status code, which will raise the matching
            ``HTTPException`` class. Or a response, which will raise a generic
            ``HTTPException`` with it as the response.
        :param args: Positional arguments passed when creating the status exception.
        :param kwargs: Keyword arguments passed when creating the status exception.
        """
        from .sansio.response import Response

        if isinstance(status, Response):
            raise HTTPException(response=status)

        if status not in self.mapping:
            raise LookupError(f"no exception for {status!r}")

        raise self.mapping[status](*args, **kwargs)


_aborter: Aborter = Aborter()


def abort(status: int | WSGIResponse, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
    """Raise an :exc:`.HTTPException` for the given status or response.

    :param status: An HTTP error status code, which will raise the matching
        ``HTTPException`` class. Or a response, which will raise a generic
        ``HTTPException`` with it as the response.
    :param args: Positional arguments passed when creating the status exception.
    :param kwargs: Keyword arguments passed when creating the status exception.
    """
    _aborter(status, *args, **kwargs)
