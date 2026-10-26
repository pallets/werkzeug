from __future__ import annotations

import collections.abc as cabc
import json
import typing as t
import wsgiref.types as wt
from http import HTTPStatus
from types import TracebackType
from urllib.parse import urljoin

from ..datastructures.headers import Headers
from ..http import _generate_etag
from ..sansio.response import Response as SansIOResponse
from ..urls import iri_to_uri
from ..utils import cached_property
from ..wsgi import _RangeWrapper
from ..wsgi import ClosingIterator

if t.TYPE_CHECKING:
    from .request import Request


def _iter_encoded(iterable: cabc.Iterable[str | bytes]) -> cabc.Iterator[bytes]:
    has_str = False
    has_bytes = False
    warned = False

    for item in iterable:
        if isinstance(item, str):
            has_str = True
            yield item.encode()
        else:
            has_bytes = True
            yield item

        if has_str and has_bytes and not warned:
            import warnings

            warned = True
            warnings.warn(
                "The response iterable must contain only bytes or only strings,"
                " not both. Support for mixed types is deprecated and will be"
                " removed in Werkzeug 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )


class Response(SansIOResponse):
    """Represents an outgoing WSGI HTTP response with body, status, and
    headers. Has properties and methods for using the functionality
    defined by various HTTP specs.

    The response body is flexible to support different use cases. The
    simple form is passing bytes, or a string which will be encoded as
    UTF-8. Passing an iterable of bytes or strings makes this a
    streaming response. A generator is particularly useful for building
    a CSV file in memory or using SSE (Server Sent Events). A file-like
    object is also iterable, although the
    :func:`~werkzeug.utils.send_file` helper should be used in that
    case.

    The response object is itself a WSGI application callable. When
    called (:meth:`__call__`) with ``environ`` and ``start_response``,
    it will pass its status and headers to ``start_response`` then
    return its body as an iterable.

    .. code-block:: python

        from werkzeug.wrappers.response import Response

        def index():
            return Response("Hello, World!")

        def application(environ, start_response):
            path = environ.get("PATH_INFO") or "/"

            if path == "/":
                response = index()
            else:
                response = Response("Not Found", status=404)

            return response(environ, start_response)

    :param response: The data for the body of the response. A string or
        bytes, or tuple or list of strings or bytes, for a fixed-length
        response, or any other iterable of strings or bytes for a
        streaming response. Defaults to an empty body.
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
    :param direct_passthrough: Pass the response body directly through
        as the WSGI iterable. This can be used when the body is a binary
        file or other iterator of bytes, to skip some unnecessary
        checks. Use :func:`~werkzeug.utils.send_file` instead of setting
        this manually.

    .. versionchanged:: 2.1
        Old ``BaseResponse`` and mixin classes were removed.

    .. versionchanged:: 2.0
        Combine ``BaseResponse`` and mixins into a single ``Response``
        class.

    .. versionchanged:: 0.5
        The ``direct_passthrough`` parameter was added.
    """

    _override_get_wsgi_headers = False
    _override_get_app_iter = False

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)

        for name, alt in (
            ("get_wsgi_headers", "apply_status"),
            ("get_app_iter", "get_wsgi_response"),
        ):
            if getattr(cls, name) is not getattr(Response, name):
                import warnings

                warnings.warn(
                    f"The '{name}' method is deprecated and will be removed in"
                    f" Werkzeug 4.0. Override '{alt}' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                setattr(cls, f"_override_{name}", True)

    implicit_sequence_conversion = True
    """Set to ``False`` to disable places where an arbitrary :attr:`response`
    iterable would be automatically converted into a fixed-length sequence. In
    that case, a ``RuntimeError`` will be raised unless ``response`` is already
    a sequence.

    .. versionchanged:: 0.6.2
        Renamed from the typo ``implicit_seqence_conversion``.
    """

    #: If a redirect ``Location`` header is a relative URL, make it an
    #: absolute URL, including scheme and domain.
    #:
    #: .. deprecated:: 3.2
    #:     Will be removed in Werkzeug 4.0. Set ``response.location`` directly
    #:     if a specific format is needed.
    #:
    #: .. versionchanged:: 2.1
    #:     This is disabled by default, so responses will send relative
    #:     redirects.
    #:
    #: .. versionadded:: 0.8
    autocorrect_location_header: None = None

    automatically_set_content_length = None
    """Set to ``False`` to disable automatically calculating and setting
    :attr:`content_length` in certain places. It can be set automatically when
    the :attr:`response` iterable is a fixed-length sequence.

    .. deprecated:: 3.2
        Will be removed in Werkzeug 4.0. Set ``response`` to a non-sequence
        iterable to indicate that the content length should not be set.

    .. versionadded:: 0.8
    """

    @property
    def _auto_length(self) -> bool:
        if self.automatically_set_content_length is None:
            return True

        import warnings

        warnings.warn(
            "The 'automatically_set_content_length' attribute is deprecated and"
            " will be removed in Werkzeug 4.0. Set 'response' to a non-sequence"
            " iterable to indicate that the content length should not be set.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.automatically_set_content_length

    response: t.Iterable[str] | t.Iterable[bytes] = ()
    """The response body to send as the WSGI iterable. A sequence with ``len``
    is a fixed-length response, any other iterable is a streaming response.

    This should contain bytes. For convenience, it can also be strings, which
    will be encoded as UTF-8.

    Use :meth:`set_data` rather than modifying this directly in most cases.

    Do not set this to a plain string or bytes. That would be very inefficient,
    as it would iterate one byte at a time.

    .. versionchanged:: 3.2
        An iterable that contains both bytes and strings is deprecated and will
        not be supported in Werkzeug 4.0.
    """

    def __init__(
        self,
        response: str | bytes | cabc.Iterable[str] | cabc.Iterable[bytes] | None = None,
        status: int | str | HTTPStatus | None = None,
        headers: cabc.Mapping[str, str | cabc.Iterable[str]]
        | cabc.Iterable[tuple[str, str]]
        | None = None,
        mimetype: str | None = None,
        content_type: str | None = None,
        direct_passthrough: bool = False,
    ) -> None:
        super().__init__(
            status=status,
            headers=headers,
            mimetype=mimetype,
            content_type=content_type,
        )

        self.direct_passthrough = direct_passthrough
        """Use :attr:`response` directly as the WSGI iterable, rather than
        passing it through :meth:`iter_encoded`. Should be enabled when
        ``response`` is a binary file. It is enabled automatically when using
        :func:`.send_file`.

        If this is set, the response's :meth:`close` method and
        :meth:`call_on_close` callbacks are not called at the end of the
        response.
        """

        self._on_close: list[t.Callable[[], t.Any]] = []

        if isinstance(response, (str, bytes)):
            self.set_data(response)
        elif response is not None:
            self.response = response

    def call_on_close(self, func: t.Callable[[], t.Any]) -> t.Callable[[], t.Any]:
        """Register additional functions to call when :meth:`close` is called.
        The WSGI server calls ``close`` when the response is done (or failed).

        If :attr:`direct_passthrough` is enabled, any registered functions will
        not be called.

        .. versionchanged:: 0.7
            Can be used as a decorator.

        .. versionadded:: 0.6
        """
        self._on_close.append(func)
        return func

    def __repr__(self) -> str:
        if self.is_sequence:
            body_info = f"{self.calculate_content_length()} bytes"
        else:
            body_info = "streamed"

        return f"<{type(self).__name__} {body_info} [{self.status}]>"

    @classmethod
    def force_type(
        cls,
        response: Response | wt.WSGIApplication,
        environ: wt.WSGIEnvironment | Request | None = None,
    ) -> t.Self:
        """Convert a response object or WSGI application to this class.

        If a response object is given, its ``__class__`` is modified in place to
        be this class. This does not create a new instance. If this class does
        something extra in ``__init__``, it will not be available.
        Use :meth:`from_app` if you need that.

        :param response: A ``Response`` object to modify in place. Or a WSGI
            application, which requires ``environ``, to run with
            :meth:`from_app`.
        :param environ: A WSGI environment or a request object, to pass to the
            WSGI application.
        """
        if not isinstance(response, Response):
            if environ is None:
                raise TypeError(
                    "cannot convert WSGI application into response"
                    " objects without an environ"
                )

            return cls.from_app(response, environ)

        response.__class__ = cls
        return response  # type: ignore[return-value]

    @classmethod
    def from_app(
        cls,
        app: wt.WSGIApplication,
        environ: wt.WSGIEnvironment | Request,
        buffered: bool = False,
    ) -> t.Self:
        """Run a WSGI application and create an instance of this response class
        with the returned body, status, and headers.

        This requires that ``__init__`` accepts ``body, status, headers`` as the
        first three positional arguments. Subclasses should not change this
        signature.

        :param app: The WSGI application. If it is a response object,
        :param environ: The WSGI environment or request object.
        :param buffered: Consume the response body iterator into a sequence.
            This can use a lot of memory, or hang if the stream is infinite.
        """
        from ..test import run_wsgi_app

        return cls(*run_wsgi_app(app, environ, buffered))

    @t.overload
    def get_data(self, as_text: t.Literal[False] = False) -> bytes: ...
    @t.overload
    def get_data(self, as_text: t.Literal[True]) -> str: ...
    def get_data(self, as_text: bool = False) -> bytes | str:
        """Read the :attr:`response` iterable into a single bytes value.

        Typically, this should only be used in tests, to examine an expected
        response. It causes ``response`` to be iterated and encoded immediately,
        which will be a problem with large or infinite streamed data.

        Set :attr:`implicit_sequence_conversion` to ``False`` to disable this
        behavior for arbitrary iterables. In that case, this can only be
        accessed if the body is already a fixed-length sequence. This cannot be
        accessed if :attr:`direct_passthrough` is ``True``.

        :param as_text: Decode the bytes as UTF-8 and return a string.

        .. versionadded:: 0.9
        """
        self._ensure_sequence()
        rv = b"".join(self.iter_encoded())

        if as_text:
            return rv.decode()

        return rv

    def _clear_body(self) -> None:
        """Clear :attr:`response`, calling its ``close`` method first.

        .. versionadded:: 3.2

        :meta private:
        """
        if (close := getattr(self.response, "close", None)) is not None:
            close()

        self.response = []

    def set_data(self, value: str | bytes) -> None:
        """Set the :attr:`response` iterable and :attr:`content_length`. A
        string is encoded as UTF-8. The value is wrapped as a single-item
        sequence.

        If the original ``response`` has a ``close`` method, it will be called
        before being replaced.

        .. versionchanged:: 3.2
            When replacing an existing iterable, calls its ``close`` method.

        .. versionadded:: 0.9
        """
        self._clear_body()

        if isinstance(value, str):
            value = value.encode()

        self.response = [value]

        if self._auto_length:
            self.content_length = len(value)

    @property
    def data(self) -> bytes:
        """The data from the response body. See :meth:`get_data` and
        :meth:`set_data`.
        """
        return self.get_data()

    @data.setter
    def data(self, value: str | bytes) -> None:
        self.set_data(value)

    def calculate_content_length(self) -> int | None:
        """Calculate the total bytes returned by the :attr:`response` iterable.

        This does not set :attr:`content_length`, it only calculates the value.
        It does not read :attr:`content_length` either, it's only based on what
        :attr:`response` contains.

        This causes ``response`` to be iterated and encoded immediately, which
        will be a problem with large or infinite streamed data.
        Set :attr:`implicit_sequence_conversion` to ``False`` to disable this
        behavior for arbitrary iterables. In that case, this can only be
        accessed if the body is already a fixed-length sequence. This cannot be
        accessed if :attr:`direct_passthrough` is ``True``.
        """
        try:
            self._ensure_sequence()
        except RuntimeError:
            return None

        return sum(map(len, self.iter_encoded()))

    def _ensure_sequence(self, mutable: None = None) -> None:
        """Use before operations that need :attr:`response` to be a
        fixed-length sequence, while obeying flags that disable this behavior.
        Use :meth:`make_sequence` to skip those checks.

        This causes ``response`` to be iterated and encoded immediately, which
        will be a problem with large or infinite streamed data.

        :raise RuntimeError: If it is not already a sequence and
            :attr:`direct_passthrough` is enabled or
            :attr:`implicit_sequence_conversion` is disabled.

        .. versionchanged:: 3.2
            The ``mutable`` parameter is deprecated and will be removed in
            Werkzeug 4.0. Build the sequence before constructing the response,
            rather than mutating it after.

        .. versionadded:: 0.6
        """
        if mutable is not None:
            import warnings

            warnings.warn(
                "The 'mutable' parameter is deprecated and will be removed in"
                " Werkzeug 4.0. Build the sequence before constructing the"
                " response, rather than mutating it after.",
                DeprecationWarning,
                stacklevel=2,
            )

        if self.is_sequence:
            if mutable and not isinstance(self.response, cabc.MutableSequence):
                self.response = list(self.response)

            return

        if self.direct_passthrough:
            raise RuntimeError(
                "Attempted implicit sequence conversion but the"
                " response object is in direct passthrough mode."
            )

        if not self.implicit_sequence_conversion:
            raise RuntimeError(
                "The response object required the iterable to be a"
                " sequence, but implicit conversion was disabled."
                " Call 'make_sequence()' manually."
            )

        self.make_sequence()

    def make_sequence(self) -> None:
        """Convert the :attr:`response` iterator to a fixed-length sequence. If
        it is already a sequence, it is left as-is. Otherwise, all items are
        joined into a single bytes value and :attr:`content_length` is set.

        If the original ``response`` has a ``close`` method, it will be called
        after iterating.

        Some other methods automatically do this conversion, but will raise an
        error instead if :attr:`direct_passthrough` is enabled or
        :attr:`implicit_sequence_conversion` is disabled. Call this method to
        skip those checks. This causes ``response`` to be iterated and encoded
        immediately, which will be a problem with large or infinite streamed
        data.

        .. versionchanged:: 3.2
            ``close`` is called immediately instead of with the response.

            Joins all items into a single bytes value.

        .. versionadded:: 0.6
        """
        if not self.is_sequence:
            self.set_data(b"".join(self.iter_encoded()))

    def iter_encoded(self) -> cabc.Iterator[bytes]:
        """Iterate over the :attr:`response` iterable as bytes. If the iterable
        is strings, they will be encoded as UTF-8.

        This is used as the WSGI iterator unless :attr:`direct_passthrough` is
        enabled. That signals that you know the ``response`` is bytes and the
        check can be skipped, which will be more efficient.

        .. versionchanged:: 3.2
            An iterable that contains both bytes and strings is deprecated and
            will not be supported in Werkzeug 4.0.
        """
        # Use a separate generator rather than yielding directly. Yielding here
        # wouldn't access `response` until the first iteration was requested,
        # meaning `r.response = process(r.iter_encoded())` would create a
        # circular reference.
        return _iter_encoded(self.response)

    @property
    def is_streamed(self) -> bool:
        """``True`` if the :attr:`response` iterable is not a sequence with a
        length, for example a generator. This means the number of iterations is
        unknown, it may end or it may be infinite.

        .. versionchanged:: 3.2
            Rejects any non ``Sequence`` instead of anything without ``len``.
        """
        return not self.is_sequence

    @property
    def is_sequence(self) -> bool:
        """``True`` if the :attr:`response` iterator is a sequence with a
        length, for example a list. This means the number of iterations is
        known, although it may change if you modify the body.

        .. versionchanged:: 3.2
            Accepts any ``Sequence`` instead of only ``list`` or ``tuple``.

        .. versionadded:: 0.6
        """
        return isinstance(self.response, cabc.Sequence)

    def close(self) -> None:
        """Call the :attr:`response` iterable's ``close`` method if it has one.
        Then calls each function registered with :meth:`call_on_close`.

        This is called automatically by the WSGI server after the response is
        done. However, if :attr:`direct_passthrough` is enabled, this is not
        used.

        .. versionadded:: 0.9
           Can be used as a ``with`` context manager.
        """
        if (close := getattr(self.response, "close", None)) is not None:
            close()

        for func in self._on_close:
            func()

    def __enter__(self) -> t.Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def freeze(self) -> None:
        """Attempt to make the response reusable. An arbitrary response cannot
        be guaranteed reusable or pickleable, even with this method.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Only reuse simple responses that
            do not depend on the current request, are fixed-length, and do not
            have callbacks.

        .. versionchanged:: 2.1
            Removed the ``no_etag`` parameter.

        .. versionchanged:: 2.0
            An ``ETag`` header is always added.

        .. versionchanged:: 0.6
            The ``Content-Length`` header is set.
        """
        import warnings

        warnings.warn(
            "The 'freeze' method is deprecated and will be removed in Werkzeug 4.0."
            " Only reuse simple responses that do not depend on the current request,"
            " are fixed-length, and do not have callbacks.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.make_sequence()
        self.add_etag()

    def get_wsgi_headers(self, environ: wt.WSGIEnvironment) -> Headers:
        """Modify and return the headers. Called by :meth:`get_wsgi_response`.

        -   ``Location`` and ``Content-Location`` are converted from IRI to URI.
        -   ``Location`` is made absolute if :attr:`autocorrect_location_header`
            is enabled.
        -   Calls :meth:`apply_status`.

        :param environ: The WSGI environment.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``apply_status`` then access
            ``headers`` instead.

            Modifies headers and body in place based on status.

            Converting from IRI to URI is deprecated and will be removed in
            Werkzeug 4.0. Set the ``location`` and ``content_location``
            properties to set these values correctly.

            ``autocorrect_location_header`` header is deprecated and will be
            removed in Werkzeug 4.0. Set the ``location`` property if you need a
            specific format.

            ``automatically_set_content_length`` is deprecated and will be
            removed in Werkzeug 4.0. ``Content-Length`` will always be set if
            the response iterable is a sequence.

        .. versionchanged:: 0.6
            Renamed from ``fix_headers``. No longer modifies the response in
            place.

            ``Location`` and ``Content-Location`` are converted from IRI to URI.
            ``Content-Length`` is set if the response iterable is a sequence.
        """
        import warnings

        warnings.warn(
            "The 'get_wsgi_headers' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'apply_status' then access 'headers' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._get_wsgi_headers(environ)
        self.apply_status()
        return self.headers

    def _get_wsgi_headers(self, environ: wt.WSGIEnvironment) -> Headers:
        if (location := self.headers.get("Location")) is not None:
            uri_location = iri_to_uri(location)

            if location != uri_location:
                import warnings

                warnings.warn(
                    "The 'Location' header must be a URI, but it was an IRI. Set"
                    " 'response.location' to handle that. An invalid header will not be"
                    " automatically corrected in Werkzeug 4.0.",
                    DeprecationWarning,
                    stacklevel=1,
                )
                self.headers["Location"] = uri_location

            if self.autocorrect_location_header:
                import warnings

                from .request import Request

                warnings.warn(
                    "Setting 'Response.autocorrect_location_header' is deprecated"
                    " and will be removed in Werkzeug 4.0. Set 'response.location'"
                    " directly if you need a specific format.",
                    DeprecationWarning,
                    stacklevel=1,
                )
                # Make the location header an absolute URL.
                current_url = iri_to_uri(Request(environ).base_url)
                self.headers["Location"] = urljoin(current_url, uri_location)

        # make sure the content location is a URL
        if (content_location := self.headers.get("Content-Location")) is not None:
            uri_content_location = iri_to_uri(content_location)

            if content_location != uri_content_location:
                import warnings

                warnings.warn(
                    "The 'Content-Location' header must be a URI, but it was an IRI."
                    " Set 'response.content_location' to handle that. An invalid header"
                    " will not be automatically corrected in Werkzeug 4.0.",
                    DeprecationWarning,
                    stacklevel=1,
                )
                self.headers["Content-Location"] = uri_content_location

        return self.headers

    def get_app_iter(self, environ: wt.WSGIEnvironment) -> cabc.Iterable[bytes]:
        """Return the body iterator for the response based on the request.

        -   Calls :meth:`apply_status`.
        -   A body is not sent for the ``HEAD`` request method.

        If :attr:`direct_passthrough` is enabled, :attr:`response` is returned
        directly, and will not call the response's :meth:`close` and
        :meth:`call_on_close` callbacks.

        :param environ: The WSGI environment.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_wsgi_response`` instead.

        .. versionadded:: 0.6
        """
        import warnings

        warnings.warn(
            "The 'get_app_iter' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_wsgi_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.apply_status()
        return self._get_app_iter(environ)

    def _get_app_iter(self, environ: wt.WSGIEnvironment) -> t.Iterable[bytes]:
        if environ.get("REQUEST_METHOD") == "HEAD":
            iterable: t.Iterable[bytes] = ()
        elif self.direct_passthrough:
            return self.response  # type: ignore[return-value]
        else:
            iterable = self.iter_encoded()

        return ClosingIterator(iterable, self.close)

    def apply_status(self) -> None:
        """Adjust the response headers and body based on its status code.

        -   Remove body and ``Content-Length`` for 1XX, 204, 205, and 304.
        -   Remove additional representation metadata (``Content-Type``,
            ``Content-Encoding``, ``Content-Language``) for 304.
        -   Set ``Content-Length`` if the body is a sequence for other statuses.

        .. versionadded:: 3.2
        """
        code = self.status_code

        if 100 <= code < 200 or code in {204, 205, 304}:
            self.headers.remove("Content-Length")
            self._clear_body()
        elif self._auto_length and self.content_length is None and self.is_sequence:
            self.content_length = self.calculate_content_length()

        if code == 304:
            # remove representation metadata
            # https://httpwg.org/specs/rfc9110.html#status.304
            # https://httpwg.org/specs/rfc9110.html#representation.metadata
            for name in ("content-type", "content-encoding", "content-language"):
                self.headers.remove(name)

    def get_wsgi_response(
        self, environ: wt.WSGIEnvironment
    ) -> tuple[cabc.Iterable[bytes], str, list[tuple[str, str]]]:
        """Produce the data needed to send a WSGI response.

        Calls :meth:`apply_status`, which may modify the headers and body
        in place.

        Modifies the returned data based on the WSGI environment. For example,
        the returned iterable is empty for a ``HEAD`` request.

        The :attr:`response` iterable is wrapped to call :meth:`close` at the
        end of the response. However, if :attr:`direct_passthrough` is enabled,
        it is not wrapped and ``close`` will not be called.

        :param environ: The WSGI environment.
        :return: ``(app_iter, status, headers)``

        .. versionchanged:: 3.2
            Modifies the headers and body in place based on the status.

        .. versionadded:: 0.6
        """
        self.apply_status()

        if self._override_get_wsgi_headers:
            headers = self.get_wsgi_headers(environ)
        else:
            headers = self._get_wsgi_headers(environ)

        if self._override_get_app_iter:
            app_iter = self.get_app_iter(environ)
        else:
            app_iter = self._get_app_iter(environ)

        return app_iter, self.status, headers.to_wsgi_list()

    def __call__(
        self, environ: wt.WSGIEnvironment, start_response: wt.StartResponse
    ) -> cabc.Iterable[bytes]:
        """Process this response as WSGI application.

        :param environ: The WSGI environment for the request.
        :param start_response: The ``start_response`` callable provided by the
            WSGI server.
        :return: An iterable with the response body.
        """
        app_iter, status, headers = self.get_wsgi_response(environ)
        start_response(status, headers)
        return app_iter

    # JSON

    #: A module or other object that has ``dumps`` and ``loads``
    #: functions that match the API of the built-in :mod:`json` module.
    json_module = json

    @property
    def json(self) -> t.Any | None:
        """The parsed JSON data if :attr:`mimetype` indicates JSON
        (:mimetype:`application/json`, see :attr:`is_json`).

        Calls :meth:`get_json` with default arguments.
        """
        return self.get_json()

    @t.overload
    def get_json(self, force: bool = ..., silent: t.Literal[False] = ...) -> t.Any: ...

    @t.overload
    def get_json(self, force: bool = ..., silent: bool = ...) -> t.Any | None: ...

    def get_json(self, force: bool = False, silent: bool = False) -> t.Any | None:
        """Parse :attr:`data` as JSON. Useful during testing.

        If the mimetype does not indicate JSON
        (:mimetype:`application/json`, see :attr:`is_json`), this
        returns ``None``.

        Unlike :meth:`Request.get_json`, the result is not cached.

        :param force: Ignore the mimetype and always try to parse JSON.
        :param silent: Silence parsing errors and return ``None``
            instead.
        """
        if not (force or self.is_json):
            return None

        data = self.get_data()

        try:
            return self.json_module.loads(data)
        except ValueError:
            if not silent:
                raise

            return None

    # Stream

    @cached_property
    def stream(self) -> ResponseStream:
        """The response iterable as write-only stream.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use a list comprehension or
            generator instead.
        """
        import warnings

        warnings.warn(
            "The 'stream' attribute is deprecated and will be removed in"
            " Werkzeug 4.0. Use a list comprehension or generator instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ResponseStream(self)

    # Preconditions and Range Requests

    def apply_conditions(self, request: Request, *, exists: bool = True) -> None:
        """Check preconditions from the request: :attr:`~.Request.if_match`,
        :attr:`~.Request.if_unmodified_since`, :attr:`~.Request.if_none_match`,
        and :attr:`~.Request.if_modified_since`. The response's :attr:`etag` and
        :attr:`last_modified` must already be set.

        Depending on the request details and the precondition, a failure will
        either raise :exc:`.PreconditionFailed`, or :attr:`status_code` will be
        set to 304. The response will handle clearing the data and content
        length for 304 automatically.

        Call :meth:`apply_range` after this, it will exit early if a condition
        was not met.

        :param request: The request to get the range from.
        :param exists: Whether the resource currently exists. Used when
            ``If-Match`` or ``If-None-Match`` are ``*``.
        :raises .PreconditionFailed: If a precondition fails and results in a
            412 instead of a 304.

        .. versionadded:: 3.2
        """
        from ..exceptions import PreconditionFailed

        etag = self.etag
        last_modified = self.last_modified

        # https://httpwg.org/specs/rfc9110.html#precedence
        # first evaluate one of if-match or if-unmodified-since
        if request.if_match:
            if not (
                exists
                if request.if_match.star_tag
                else request.if_match.contains_strong(etag)
            ):
                raise PreconditionFailed()
        else:
            if (
                request.if_unmodified_since is not None
                and last_modified is not None
                and last_modified > request.if_unmodified_since
            ):
                raise PreconditionFailed()

        # then evaluate one of if-none-match or if-modified-since
        if request.if_none_match:
            if (
                exists
                if request.if_none_match.star_tag
                else request.if_none_match.contains_weak(etag)
            ):
                if request.method not in {"GET", "HEAD"}:
                    raise PreconditionFailed()

                self.status_code = 304
                self.apply_status()
        else:
            if (
                request.method in {"GET", "HEAD"}
                and last_modified is not None
                and request.if_modified_since is not None
                and last_modified <= request.if_modified_since
            ):
                self.status_code = 304
                self.apply_status()

    def apply_range(self, request: Request) -> None:
        """Advertise range request support, check :attr:`.Request.if_range`, and
        apply :attr:`.Request.range` if it is valid and satisfiable. The
        response's :attr:`data`, :attr:`content_length`, :attr:`etag`, and
        :attr:`last_modified` must already be set for the complete data.

        Only the ``bytess`` unit is supported. If multiple ranges are given,
        only the first is used. An unknown length is not supported.

        Call :meth:`apply_conditions` before this, to exit early if a condition
        was not met.

        :param request: The request to get the range from.
        :raises .RequestedRangeNotSatisfiable: If the range is valid but cannot
            be satisfied for the content length.

        .. versionadded:: 3.2
        """
        from ..exceptions import RequestedRangeNotSatisfiable

        self.accept_ranges = "bytes"

        if (
            self.status_code != 200
            or request.method != "GET"
            or request.range is None
            or request.range.units != "bytes"
            or not (complete_length := self.content_length)
            or (
                request.if_range
                and not request.if_range.check(self.etag, self.last_modified)
            )
        ):
            return

        if (content_range := request.range.make_content_range(complete_length)) is None:
            raise RequestedRangeNotSatisfiable(complete_length)

        content_length = content_range.stop - content_range.start  # type: ignore[operator]
        self.content_length = content_length
        self.content_range = content_range
        self.status_code = 206
        self.response = _RangeWrapper(
            self.response,  # type: ignore[arg-type]
            content_range.start,  # type: ignore[arg-type]
            content_length,
        )

    def make_conditional(
        self,
        request_or_environ: Request | wt.WSGIEnvironment,
        accept_ranges: bool = False,
        complete_length: int | None = None,
    ) -> Response:
        """Check preconditions from the request, advertise range support, and
        apply a requested range. :attr:`data`, :attr:`content_length`,
        :attr:`etag`, and :attr:`last_modified` must already be set.

        :param request_or_environ: The request or WSGI environ to get the
            preconditions and range from.
        :param accept_ranges: If ``True``, after checking preconditions,
            advertise range support and apply a requested range.
        :param complete_length: Set :attr:`content_length` to this value. Better
            to set it before calling instead.
        :raises .PreconditionFailed: If a precondition fails and results in a
            412 instead of a 304.
        :raises .RequestedRangeNotSatisfiable: If the range is valid but cannot
            be satisfied for the content length.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 3.3. Use ``apply_conditions`` and
            ``apply_range`` instead.

        .. versionchanged:: 3.2
            Applies to all request methods correctly.

            Does not set ``Date``. Does not calculate ``Content-Length``
            if not given.

            Correct ordering of preconditions followed by range.

            Only the ``bytes`` unit is allowed. Sets ``Accept-Ranges``
            even if the range is not valid or satisfiable.

            Raises ``PreconditionFailed`` instead of setting a ``412`` status.

        .. versionchanged:: 2.0
            Range processing is skipped if length is 0 instead of raising a 416.
        """
        import warnings

        warnings.warn(
            "'make_conditional' is deprecated and will be removed in Werkzeug 3.3."
            " Use 'apply_conditions' and 'apply_range' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from .request import Request

        if isinstance(request_or_environ, Request):
            request = request_or_environ
        else:
            request = Request(request_or_environ)

        self.apply_conditions(request)

        if accept_ranges:
            if complete_length is not None:
                self.content_length = complete_length

            self.apply_range(request)

        return self

    def add_etag(self, overwrite: bool = False, weak: bool = False) -> None:
        """Set the ``ETag`` header by hashing the response's data. This causes
        the data to be read, don't call this on a streaming response.

        :param overwrite: Overwrite an existing ``ETag`` header.
        :param weak: Mark the ETag as weak. This is unlikely what you want, as
            a hash of the data is typically considered strong.

        .. versionchanged:: 3.2
            Use SHA3-256.

        .. versionchanged:: 2.0
            Use SHA-1.
        """
        if overwrite or "ETag" not in self.headers:
            self.etag = _generate_etag(self.get_data()), weak


class ResponseStream:
    """A file descriptor like object used by :meth:`Response.stream` to
    represent the body of the stream. It directly pushes into the
    response iterable of the response object.
    """

    mode = "wb+"

    def __init__(self, response: Response):
        self.response = response
        self.closed = False

    def write(self, value: bytes) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        self.response._ensure_sequence(mutable=True)  # type: ignore[arg-type]
        self.response.response.append(value)  # type: ignore[union-attr]
        self.response.content_length = None
        return len(value)

    def writelines(self, seq: cabc.Iterable[bytes]) -> None:
        for item in seq:
            self.write(item)

    def close(self) -> None:
        self.closed = True

    def flush(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def isatty(self) -> bool:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return False

    def tell(self) -> int:
        self.response._ensure_sequence()
        return sum(map(len, self.response.response))

    @property
    def encoding(self) -> str:
        return "utf-8"
