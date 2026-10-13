from __future__ import annotations

import collections.abc as cabc
import json
import typing as t
from http import HTTPStatus
from types import TracebackType
from urllib.parse import urljoin

from ..datastructures.headers import Headers
from ..http import _generate_etag
from ..sansio.response import Response as _SansIOResponse
from ..urls import iri_to_uri
from ..utils import cached_property
from ..wsgi import _RangeWrapper
from ..wsgi import ClosingIterator

if t.TYPE_CHECKING:
    from _typeshed.wsgi import StartResponse
    from _typeshed.wsgi import WSGIApplication
    from _typeshed.wsgi import WSGIEnvironment

    from .request import Request


def _iter_encoded(iterable: t.Iterable[str | bytes]) -> t.Iterator[bytes]:
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


class Response(_SansIOResponse):
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

    automatically_set_content_length = True
    """Set to ``False`` to disable automatically calculating and setting
    :attr:`content_length` in certain places. It can be set automatically when
    the :attr:`response` iterable is a fixed-length sequence.

    .. versionadded:: 0.8
    """

    response: t.Iterable[str] | t.Iterable[bytes]
    """The response body to send as the WSGI iterable. A sequence with ``len``
    is a fixed-length response, any other iterable is a streaming response.

    This should contain bytes. For convenience, it can also be strings, which
    will be encoded as UTF-8. If you know the body is bytes, set
    :attr:`direct_passthrough` to avoid some overhead.

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
        headers: t.Mapping[str, str | t.Iterable[str]]
        | t.Iterable[tuple[str, str]]
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
        """

        self._on_close: list[t.Callable[[], t.Any]] = []

        # Can't call set_data(response) for all types here, it may clear the
        # content-type header.
        if response is None:
            self.response = []
        elif isinstance(response, (str, bytes)):
            self.set_data(response)
        else:
            self.response = response

    def call_on_close(self, func: t.Callable[[], t.Any]) -> t.Callable[[], t.Any]:
        """Adds a function to the internal list of functions that should
        be called as part of closing down the response.  Since 0.7 this
        function also returns the function that was passed so that this
        can be used as a decorator.

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
        response: Response | WSGIApplication,
        environ: WSGIEnvironment | None = None,
    ) -> Response:
        """Enforce that the WSGI response is a response object of the current
        type.  Werkzeug will use the :class:`Response` internally in many
        situations like the exceptions.  If you call :meth:`get_response` on an
        exception you will get back a regular :class:`Response` object, even
        if you are using a custom subclass.

        This method can enforce a given response type, and it will also
        convert arbitrary WSGI callables into response objects if an environ
        is provided::

            # convert a Werkzeug response object into an instance of the
            # MyResponseClass subclass.
            response = MyResponseClass.force_type(response)

            # convert any WSGI application into a response object
            response = MyResponseClass.force_type(response, environ)

        This is especially useful if you want to post-process responses in
        the main dispatcher and use functionality provided by your subclass.

        Keep in mind that this will modify response objects in place if
        possible!

        :param response: a response object or wsgi application.
        :param environ: a WSGI environment object.
        :return: a response object.
        """
        if not isinstance(response, Response):
            if environ is None:
                raise TypeError(
                    "cannot convert WSGI application into response"
                    " objects without an environ"
                )

            from ..test import run_wsgi_app

            response = Response(*run_wsgi_app(response, environ))

        response.__class__ = cls
        return response

    @classmethod
    def from_app(
        cls, app: WSGIApplication, environ: WSGIEnvironment, buffered: bool = False
    ) -> Response:
        """Create a new response object from an application output.  This
        works best if you pass it an application that returns a generator all
        the time.  Sometimes applications may use the `write()` callable
        returned by the `start_response` function.  This tries to resolve such
        edge cases automatically.  But if you don't get the expected output
        you should set `buffered` to `True` which enforces buffering.

        :param app: the WSGI application to execute.
        :param environ: the WSGI environment to execute against.
        :param buffered: set to `True` to enforce buffering.
        :return: a response object.
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

    def set_data(self, value: str | bytes) -> None:
        """Set the :attr:`response` iterable and :attr:`content_length`. A
        string is encoded as UTF-8. The value is wrapped as a single-item
        sequence.nse.

        .. versionadded:: 0.9
        """
        if isinstance(value, str):
            value = value.encode()

        self.response = [value]

        if self.automatically_set_content_length:
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

    def _ensure_sequence(self, mutable: bool = False) -> None:
        """Use before operations that need :attr:`response` to be a
        fixed-length sequence, while obeying flags that disable this behavior.
        Use :meth:`make_sequence` to override those flags.

        This causes ``response`` to be iterated and encoded immediately, which
        will be a problem with large or infinite streamed data.

        :param mutable: Convert to a mutable sequence.
        :raise RuntimeError: If it is not already a sequence and
            :attr:direct_passthrough` is enabled or
            :attr:`implicit_sequence_conversion` is disabled.

        .. versionadded:: 0.6
        """
        if self.is_sequence:
            if mutable and not isinstance(self.response, cabc.MutableSequence):
                self.response = list(self.response)  # type: ignore[assignment]

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
        """Convert the :attr:`response` iterator to a fixed-length sequence if
        it is not already.

        Sets :attr:`content_length` unless :attr:`automatically_set_content_length`
        is disabled.

        If the original ``response`` has a ``close`` method, it will be called
        after iterating.

        Some other methods automatically do this conversion, but will raise an
        error instead if :attr:`direct_passthrough` is enabled or
        :attr:`implicit_sequence_conversion` is disabled. Call this method to
        override those checks. This causes ``response`` to be iterated and
        encoded immediately, which will be a problem with large or infinite
        streamed data.

        .. versionchanged:: 3.2
            ``close`` is called immediately instead of with the response.

        .. versionadded:: 0.6
        """
        if not self.is_sequence:
            close: t.Callable[[], None] | None = getattr(self.response, "close", None)
            self.response = list(self.iter_encoded())

            if close is not None:
                close()

    def iter_encoded(self) -> t.Iterator[bytes]:
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
        """Close the wrapped response if possible.  You can also use the object
        in a with statement which will automatically close it.

        .. versionadded:: 0.9
           Can now be used in a with statement.
        """
        if hasattr(self.response, "close"):
            self.response.close()
        for func in self._on_close:
            func()

    def __enter__(self) -> Response:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def freeze(self) -> None:
        """Make the response pickleable.

        -   Call :attr:`make_sequence` to buffer the response in memory,
            ignoring :attr:`direct_passthrough` and
            :attr:`implicit_sequence_conversion`.
        -   Set :attr:`content_length` to :meth:`calculate_content_length`, even
            if it's already set.
        -   Call :attr:`add_etag` to generate an ``ETag`` header if it's not
            already set.

        .. versionchanged:: 2.1
            Removed the ``no_etag`` parameter.

        .. versionchanged:: 2.0
            An ``ETag`` header is always added.

        .. versionchanged:: 0.6
            The ``Content-Length`` header is set.
        """
        self.make_sequence()
        self.content_length = self.calculate_content_length()
        self.add_etag()

    def get_wsgi_headers(self, environ: WSGIEnvironment) -> Headers:
        """This is automatically called right before the response is started
        and returns headers modified for the given environment.  It returns a
        copy of the headers from the response with some modifications applied
        if necessary.

        For example the location header (if present) is joined with the root
        URL of the environment.  Also the content length is automatically set
        to zero here for certain status codes.

        .. versionchanged:: 0.6
           Previously that function was called `fix_headers` and modified
           the response object in place.  Also since 0.6, IRIs in location
           and content-location headers are handled properly.

           Also starting with 0.6, Werkzeug will attempt to set the content
           length if it is able to figure it out on its own.  This is the
           case if all the strings in the response iterable are already
           encoded and the iterable is buffered.

        :param environ: the WSGI environment of the request.
        :return: returns a new :class:`~werkzeug.datastructures.Headers`
                 object.
        """
        headers = Headers(self.headers)
        location: str | None = None
        content_location: str | None = None
        content_length: str | None = None
        status = self.status_code

        # iterate over the headers to find all values in one go.  Because
        # get_wsgi_headers is used each response that gives us a tiny
        # speedup.
        for key, value in headers:
            ikey = key.lower()
            if ikey == "location":
                location = value
            elif ikey == "content-location":
                content_location = value
            elif ikey == "content-length":
                content_length = value

        if location is not None:
            location = iri_to_uri(location)

            if self.autocorrect_location_header:
                import warnings

                from .request import Request

                warnings.warn(
                    "Setting 'Response.autocorrect_location_header' is deprecated"
                    " and will be removed in Werkzeug 4.0. Set 'response.location'"
                    " directly if you need a specific format.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                # Make the location header an absolute URL.
                current_url = iri_to_uri(Request(environ).base_url)
                location = urljoin(current_url, location)

            headers["Location"] = location

        # make sure the content location is a URL
        if content_location is not None:
            headers["Content-Location"] = iri_to_uri(content_location)

        if 100 <= status < 200 or status == 204:
            # Per section 3.3.2 of RFC 7230, "a server MUST NOT send a
            # Content-Length header field in any response with a status
            # code of 1xx (Informational) or 204 (No Content)."
            headers.remove("Content-Length")
        elif status == 304:
            # remove representation metadata
            # https://httpwg.org/specs/rfc9110.html#status.304
            # https://httpwg.org/specs/rfc9110.html#representation.metadata
            for name in (
                "content-type",
                "content-encoding",
                "content-language",
                "content-length",
            ):
                headers.remove(name)

        # if we can determine the content length automatically, we
        # should try to do that.  But only if this does not involve
        # flattening the iterator or encoding of strings in the
        # response. We however should not do that if we have a 304
        # response.
        if (
            self.automatically_set_content_length
            and content_length is None
            and self.is_sequence
            and status not in (204, 304)
            and not (100 <= status < 200)
        ):
            headers["Content-Length"] = str(self.calculate_content_length())

        return headers

    def get_app_iter(self, environ: WSGIEnvironment) -> t.Iterable[bytes]:
        """Returns the application iterator for the given environ.  Depending
        on the request method and the current status code the return value
        might be an empty response rather than the one from the response.

        If the request method is `HEAD` or the status code is in a range
        where the HTTP specification requires an empty response, an empty
        iterable is returned.

        .. versionadded:: 0.6

        :param environ: the WSGI environment of the request.
        :return: a response iterable.
        """
        status = self.status_code
        if (
            environ["REQUEST_METHOD"] == "HEAD"
            or 100 <= status < 200
            or status in (204, 304)
        ):
            iterable: t.Iterable[bytes] = ()
        elif self.direct_passthrough:
            return self.response  # type: ignore[return-value]
        else:
            iterable = self.iter_encoded()
        return ClosingIterator(iterable, self.close)

    def get_wsgi_response(
        self, environ: WSGIEnvironment
    ) -> tuple[t.Iterable[bytes], str, list[tuple[str, str]]]:
        """Returns the final WSGI response as tuple.  The first item in
        the tuple is the application iterator, the second the status and
        the third the list of headers.  The response returned is created
        specially for the given environment.  For example if the request
        method in the WSGI environment is ``'HEAD'`` the response will
        be empty and only the headers and status code will be present.

        .. versionadded:: 0.6

        :param environ: the WSGI environment of the request.
        :return: an ``(app_iter, status, headers)`` tuple.
        """
        headers = self.get_wsgi_headers(environ)
        app_iter = self.get_app_iter(environ)
        return app_iter, self.status, headers.to_wsgi_list()

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> t.Iterable[bytes]:
        """Process this response as WSGI application.

        :param environ: the WSGI environment.
        :param start_response: the response callable provided by the WSGI
                               server.
        :return: an application iterator
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
        else:
            if (
                request.method in {"GET", "HEAD"}
                and last_modified is not None
                and request.if_modified_since is not None
                and last_modified <= request.if_modified_since
            ):
                self.status_code = 304

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
        request_or_environ: Request | WSGIEnvironment,
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
        self.response._ensure_sequence(mutable=True)
        self.response.response.append(value)  # type: ignore[union-attr]
        self.response.content_length = None
        return len(value)

    def writelines(self, seq: t.Iterable[bytes]) -> None:
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
