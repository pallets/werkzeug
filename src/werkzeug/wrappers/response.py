import json
import typing
import typing as t
import warnings
from datetime import datetime
from datetime import timedelta

from .._internal import _to_bytes
from .._internal import _to_str
from ..datastructures import Headers
from ..http import dump_cookie
from ..http import HTTP_STATUS_CODES
from ..http import remove_entity_headers
from ..urls import iri_to_uri
from ..urls import url_join
from ..utils import cached_property
from ..utils import get_content_type
from ..wsgi import ClosingIterator
from ..wsgi import get_current_url
from werkzeug._internal import _get_environ
from werkzeug.datastructures import CallbackDict
from werkzeug.datastructures import ContentRange
from werkzeug.datastructures import ResponseCacheControl
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.http import dump_age
from werkzeug.http import dump_csp_header
from werkzeug.http import dump_header
from werkzeug.http import dump_options_header
from werkzeug.http import generate_etag
from werkzeug.http import http_date
from werkzeug.http import is_resource_modified
from werkzeug.http import parse_age
from werkzeug.http import parse_cache_control_header
from werkzeug.http import parse_content_range_header
from werkzeug.http import parse_csp_header
from werkzeug.http import parse_date
from werkzeug.http import parse_etags
from werkzeug.http import parse_options_header
from werkzeug.http import parse_range_header
from werkzeug.http import parse_set_header
from werkzeug.http import parse_www_authenticate_header
from werkzeug.http import quote_etag
from werkzeug.http import unquote_etag
from werkzeug.utils import header_property
from werkzeug.wsgi import _RangeWrapper

if t.TYPE_CHECKING:
    from wsgiref.types import StartResponse
    from wsgiref.types import WSGIApplication
    from wsgiref.types import WSGIEnvironment


def _warn_if_string(iterable: t.Iterable) -> None:
    """Helper for the response objects to check if the iterable returned
    to the WSGI server is not a string.
    """
    if isinstance(iterable, str):
        warnings.warn(
            "Response iterable was set to a string. This will appear to"
            " work but means that the server will send the data to the"
            " client one character at a time. This is almost never"
            " intended behavior, use 'response.data' to assign strings"
            " to the response object.",
            stacklevel=2,
        )


def _iter_encoded(
    iterable: t.Iterable[t.Union[str, bytes]], charset: str
) -> t.Iterator[bytes]:
    for item in iterable:
        if isinstance(item, str):
            yield item.encode(charset)
        else:
            yield item


def _clean_accept_ranges(accept_ranges: t.Union[bool, str]) -> str:
    if accept_ranges is True:
        return "bytes"
    elif accept_ranges is False:
        return "none"
    elif isinstance(accept_ranges, str):
        return accept_ranges
    raise ValueError("Invalid accept_ranges value")


def _set_property(name: str, doc: t.Optional[str] = None) -> property:
    def fget(self):
        def on_update(header_set):
            if not header_set and name in self.headers:
                del self.headers[name]
            elif header_set:
                self.headers[name] = header_set.to_header()

        return parse_set_header(self.headers.get(name), on_update)

    def fset(self, value):
        if not value:
            del self.headers[name]
        elif isinstance(value, str):
            self.headers[name] = value
        else:
            self.headers[name] = dump_header(value)

    return property(fget, fset, doc=doc)


class Response:
    """Represents an outgoing HTTP response with body, status, and
    headers. Has properties and methods for using the
    functionality defined by various HTTP specs.

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

    .. versionchanged:: 2.0
        Combine ``BaseResponse`` and mixins into a single ``Response``
        class. Using the old classes is deprecated and will be removed
        in version 2.1.

    .. versionchanged:: 0.5
        The ``direct_passthrough`` parameter was added.
    """

    #: the charset of the response.
    charset = "utf-8"

    #: the default status if none is provided.
    default_status = 200

    #: the default mimetype if none is provided.
    default_mimetype = "text/plain"

    #: if set to `False` accessing properties on the response object will
    #: not try to consume the response iterator and convert it into a list.
    #:
    #: .. versionadded:: 0.6.2
    #:
    #:    That attribute was previously called `implicit_seqence_conversion`.
    #:    (Notice the typo).  If you did use this feature, you have to adapt
    #:    your code to the name change.
    implicit_sequence_conversion = True

    #: Should this response object correct the location header to be RFC
    #: conformant?  This is true by default.
    #:
    #: .. versionadded:: 0.8
    autocorrect_location_header = True

    #: Should this response object automatically set the content-length
    #: header if possible?  This is true by default.
    #:
    #: .. versionadded:: 0.8
    automatically_set_content_length = True

    #: Warn if a cookie header exceeds this size. The default, 4093, should be
    #: safely `supported by most browsers <cookie_>`_. A cookie larger than
    #: this size will still be sent, but it may be ignored or handled
    #: incorrectly by some browsers. Set to 0 to disable this check.
    #:
    #: .. versionadded:: 0.13
    #:
    #: .. _`cookie`: http://browsercookielimits.squawky.net/
    max_cookie_size = 4093

    #: The response body to send as the WSGI iterable. A list of strings
    #: or bytes represents a fixed-length response, any other iterable
    #: is a streaming response. Strings are encoded to bytes as UTF-8.
    #:
    #: Do not set to a plain string or bytes, that will cause sending
    #: the response to be very inefficient as it will iterate one byte
    #: at a time.
    response: t.Union[t.Iterable[str], t.Iterable[bytes]]

    # A :class:`Headers` object representing the response headers.
    headers: Headers

    def __init__(
        self,
        response: t.Optional[
            t.Union[t.Iterable[bytes], bytes, t.Iterable[str], str]
        ] = None,
        status: t.Optional[t.Union[int, str]] = None,
        headers: t.Optional[
            t.Union[
                t.Mapping[str, t.Union[str, int, t.Iterable[t.Union[str, int]]]],
                t.Iterable[t.Tuple[str, t.Union[str, int]]],
            ]
        ] = None,
        mimetype: t.Optional[str] = None,
        content_type: t.Optional[str] = None,
        direct_passthrough: bool = False,
    ) -> None:
        if isinstance(headers, Headers):
            self.headers = headers
        elif not headers:
            self.headers = Headers()
        else:
            self.headers = Headers(headers)

        if content_type is None:
            if mimetype is None and "content-type" not in self.headers:
                mimetype = self.default_mimetype
            if mimetype is not None:
                mimetype = get_content_type(mimetype, self.charset)
            content_type = mimetype
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        if status is None:
            status = self.default_status
        self.status = status  # type: ignore

        #: Pass the response body directly through as the WSGI iterable.
        #: This can be used when the body is a binary file or other
        #: iterator of bytes, to skip some unnecessary checks. Use
        #: :func:`~werkzeug.utils.send_file` instead of setting this
        #: manually.
        self.direct_passthrough = direct_passthrough
        self._on_close: t.List[t.Callable[[], t.Any]] = []

        # we set the response after the headers so that if a class changes
        # the charset attribute, the data is set in the correct charset.
        if response is None:
            self.response = []
        elif isinstance(response, (str, bytes, bytearray)):
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
            body_info = f"{sum(map(len, self.iter_encoded()))} bytes"
        else:
            body_info = "streamed" if self.is_streamed else "likely-streamed"
        return f"<{type(self).__name__} {body_info} [{self.status}]>"

    @classmethod
    def force_type(
        cls, response: "Response", environ: t.Optional["WSGIEnvironment"] = None
    ) -> "Response":
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
        cls, app: "WSGIApplication", environ: "WSGIEnvironment", buffered: bool = False
    ) -> "Response":
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

    @property
    def status_code(self) -> int:
        """The HTTP status code as a number."""
        return self._status_code

    @status_code.setter
    def status_code(self, code: int) -> None:
        self.status = code  # type: ignore

    @property
    def status(self) -> str:
        """The HTTP status code as a string."""
        return self._status

    @status.setter
    def status(self, value: t.Union[str, int]) -> None:
        if not isinstance(value, (str, bytes, int)):
            raise TypeError("Invalid status argument")

        self._status, self._status_code = self._clean_status(value)

    def _clean_status(self, value: t.Union[str, int]) -> t.Tuple[str, int]:
        status = _to_str(value, self.charset)
        split_status = status.split(None, 1)

        if len(split_status) == 0:
            raise ValueError("Empty status argument")

        if len(split_status) > 1:
            if split_status[0].isdigit():
                # code and message
                return status, int(split_status[0])

            # multi-word message
            return f"0 {status}", 0

        if split_status[0].isdigit():
            # code only
            status_code = int(split_status[0])

            try:
                status = f"{status_code} {HTTP_STATUS_CODES[status_code].upper()}"
            except KeyError:
                status = f"{status_code} UNKNOWN"

            return status, status_code

        # one-word message
        return f"0 {status}", 0

    @typing.overload
    def get_data(self, as_text: "t.Literal[False]" = False) -> bytes:
        ...

    @typing.overload
    def get_data(self, as_text: "t.Literal[True]") -> str:
        ...

    def get_data(self, as_text=False):
        """The string representation of the response body.  Whenever you call
        this property the response iterable is encoded and flattened.  This
        can lead to unwanted behavior if you stream big data.

        This behavior can be disabled by setting
        :attr:`implicit_sequence_conversion` to `False`.

        If `as_text` is set to `True` the return value will be a decoded
        string.

        .. versionadded:: 0.9
        """
        self._ensure_sequence()
        rv = b"".join(self.iter_encoded())
        if as_text:
            rv = rv.decode(self.charset)
        return rv

    def set_data(self, value: t.Union[bytes, str]) -> None:
        """Sets a new string as response.  The value must be a string or
        bytes. If a string is set it's encoded to the charset of the
        response (utf-8 by default).

        .. versionadded:: 0.9
        """
        # if a string is set, it's encoded directly so that we
        # can set the content length
        if isinstance(value, str):
            value = value.encode(self.charset)
        else:
            value = bytes(value)
        self.response = [value]
        if self.automatically_set_content_length:
            self.headers["Content-Length"] = str(len(value))

    data = property(
        get_data,
        set_data,
        doc="A descriptor that calls :meth:`get_data` and :meth:`set_data`.",
    )

    def calculate_content_length(self) -> t.Optional[int]:
        """Returns the content length if available or `None` otherwise."""
        try:
            self._ensure_sequence()
        except RuntimeError:
            return None
        return sum(len(x) for x in self.iter_encoded())

    def _ensure_sequence(self, mutable: bool = False) -> None:
        """This method can be called by methods that need a sequence.  If
        `mutable` is true, it will also ensure that the response sequence
        is a standard Python list.

        .. versionadded:: 0.6
        """
        if self.is_sequence:
            # if we need a mutable object, we ensure it's a list.
            if mutable and not isinstance(self.response, list):
                self.response = list(self.response)  # type: ignore
            return
        if self.direct_passthrough:
            raise RuntimeError(
                "Attempted implicit sequence conversion but the"
                " response object is in direct passthrough mode."
            )
        if not self.implicit_sequence_conversion:
            raise RuntimeError(
                "The response object required the iterable to be a"
                " sequence, but the implicit conversion was disabled."
                " Call make_sequence() yourself."
            )
        self.make_sequence()

    def make_sequence(self) -> None:
        """Converts the response iterator in a list.  By default this happens
        automatically if required.  If `implicit_sequence_conversion` is
        disabled, this method is not automatically called and some properties
        might raise exceptions.  This also encodes all the items.

        .. versionadded:: 0.6
        """
        if not self.is_sequence:
            # if we consume an iterable we have to ensure that the close
            # method of the iterable is called if available when we tear
            # down the response
            close = getattr(self.response, "close", None)
            self.response = list(self.iter_encoded())
            if close is not None:
                self.call_on_close(close)

    def iter_encoded(self) -> t.Iterator[bytes]:
        """Iter the response encoded with the encoding of the response.
        If the response object is invoked as WSGI application the return
        value of this method is used as application iterator unless
        :attr:`direct_passthrough` was activated.
        """
        if __debug__:
            _warn_if_string(self.response)
        # Encode in a separate function so that self.response is fetched
        # early.  This allows us to wrap the response with the return
        # value from get_app_iter or iter_encoded.
        return _iter_encoded(self.response, self.charset)

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: t.Optional[t.Union[timedelta, int]] = None,
        expires: t.Optional[t.Union[str, datetime, int, float]] = None,
        path: t.Optional[str] = "/",
        domain: t.Optional[str] = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Optional[str] = None,
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
                       ``domain=".example.com"`` will set a cookie that is
                       readable by the domain ``www.example.com``,
                       ``foo.example.com`` etc.  Otherwise, a cookie will only
                       be readable by the domain that set it.
        :param secure: If ``True``, the cookie will only be available
            via HTTPS.
        :param httponly: Disallow JavaScript access to the cookie.
        :param samesite: Limit the scope of the cookie to only be
            attached to requests that are "same-site".
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
                charset=self.charset,
                max_size=self.max_cookie_size,
                samesite=samesite,
            ),
        )

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: t.Optional[str] = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Optional[str] = None,
    ):
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
        )

    @property
    def is_streamed(self) -> bool:
        """If the response is streamed (the response is not an iterable with
        a length information) this property is `True`.  In this case streamed
        means that there is no information about the number of iterations.
        This is usually `True` if a generator is passed to the response object.

        This is useful for checking before applying some sort of post
        filtering that should not take place for streamed responses.
        """
        try:
            len(self.response)  # type: ignore
        except (TypeError, AttributeError):
            return True
        return False

    @property
    def is_sequence(self) -> bool:
        """If the iterator is buffered, this property will be `True`.  A
        response object will consider an iterator to be buffered if the
        response attribute is a list or tuple.

        .. versionadded:: 0.6
        """
        return isinstance(self.response, (tuple, list))

    def close(self) -> None:
        """Close the wrapped response if possible.  You can also use the object
        in a with statement which will automatically close it.

        .. versionadded:: 0.9
           Can now be used in a with statement.
        """
        if hasattr(self.response, "close"):
            self.response.close()  # type: ignore
        for func in self._on_close:
            func()

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def freeze(self, no_etag: None = None) -> None:
        """Make the response object ready to be pickled. Does the
        following:

        *   Buffer the response into a list, ignoring
            :attr:`implicity_sequence_conversion` and
            :attr:`direct_passthrough`.
        *   Set the ``Content-Length`` header.
        *   Generate an ``ETag`` header if one is not already set.

        .. versionchanged:: 2.0
            An ``ETag`` header is added, the ``no_etag`` parameter is
            deprecated and will be removed in version 2.1.

        .. versionchanged:: 0.6
            The ``Content-Length`` header is set.
        """
        # Always freeze the encoded response body, ignore
        # implicit_sequence_conversion and direct_passthrough.
        self.response = list(self.iter_encoded())
        self.headers["Content-Length"] = str(sum(map(len, self.response)))

        if no_etag is not None:
            warnings.warn(
                "The 'no_etag' parameter is deprecated and will be"
                " removed in Werkzeug version 2.1.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.add_etag()

    def get_wsgi_headers(self, environ: "WSGIEnvironment") -> Headers:
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
        location: t.Optional[str] = None
        content_location: t.Optional[str] = None
        content_length: t.Optional[t.Union[str, int]] = None
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

        # make sure the location header is an absolute URL
        if location is not None:
            old_location = location
            if isinstance(location, str):
                # Safe conversion is necessary here as we might redirect
                # to a broken URI scheme (for instance itms-services).
                location = iri_to_uri(location, safe_conversion=True)

            if self.autocorrect_location_header:
                current_url = get_current_url(environ, strip_querystring=True)
                if isinstance(current_url, str):
                    current_url = iri_to_uri(current_url)
                location = url_join(current_url, location)
            if location != old_location:
                headers["Location"] = location  # type: ignore

        # make sure the content location is a URL
        if content_location is not None and isinstance(content_location, str):
            headers["Content-Location"] = iri_to_uri(content_location)

        if 100 <= status < 200 or status == 204:
            # Per section 3.3.2 of RFC 7230, "a server MUST NOT send a
            # Content-Length header field in any response with a status
            # code of 1xx (Informational) or 204 (No Content)."
            headers.remove("Content-Length")
        elif status == 304:
            remove_entity_headers(headers)

        # if we can determine the content length automatically, we
        # should try to do that.  But only if this does not involve
        # flattening the iterator or encoding of strings in the
        # response. We however should not do that if we have a 304
        # response.
        if (
            self.automatically_set_content_length
            and self.is_sequence
            and content_length is None
            and status not in (204, 304)
            and not (100 <= status < 200)
        ):
            try:
                content_length = sum(len(_to_bytes(x, "ascii")) for x in self.response)
            except UnicodeError:
                # Something other than bytes, can't safely figure out
                # the length of the response.
                pass
            else:
                headers["Content-Length"] = str(content_length)

        return headers

    def get_app_iter(self, environ: "WSGIEnvironment") -> t.Iterable[bytes]:
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
            if __debug__:
                _warn_if_string(self.response)
            return self.response  # type: ignore
        else:
            iterable = self.iter_encoded()
        return ClosingIterator(iterable, self.close)

    def get_wsgi_response(
        self, environ: "WSGIEnvironment"
    ) -> t.Tuple[t.Iterable[bytes], str, t.List[t.Tuple[str, str]]]:
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
        self, environ: "WSGIEnvironment", start_response: "StartResponse"
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
    def json(self) -> t.Optional[t.Any]:
        """The parsed JSON data if :attr:`mimetype` indicates JSON
        (:mimetype:`application/json`, see :meth:`is_json`).

        Calls :meth:`get_json` with default arguments.
        """
        return self.get_json()

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

    def get_json(self, force: bool = False, silent: bool = False) -> t.Optional[t.Any]:
        """Parse :attr:`data` as JSON. Useful during testing.

        If the mimetype does not indicate JSON
        (:mimetype:`application/json`, see :meth:`is_json`), this
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
    def stream(self) -> "ResponseStream":
        """The response iterable as write-only stream."""
        return ResponseStream(self)

    # Common Descriptors

    @property
    def mimetype(self) -> t.Optional[str]:
        """The mimetype (content type without charset etc.)"""
        ct = self.headers.get("content-type")

        if ct:
            return ct.split(";")[0].strip()
        else:
            return None

    @mimetype.setter
    def mimetype(self, value: str) -> None:
        self.headers["Content-Type"] = get_content_type(value, self.charset)

    @property
    def mimetype_params(self) -> t.Dict[str, str]:
        """The mimetype parameters as dict. For example if the
        content type is ``text/html; charset=utf-8`` the params would be
        ``{'charset': 'utf-8'}``.

        .. versionadded:: 0.5
        """

        def on_update(d):
            self.headers["Content-Type"] = dump_options_header(self.mimetype, d)

        d = parse_options_header(self.headers.get("content-type", ""))[1]
        return CallbackDict(d, on_update)

    location = header_property[str](
        "Location",
        doc="""The Location response-header field is used to redirect
        the recipient to a location other than the Request-URI for
        completion of the request or identification of a new
        resource.""",
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
    content_md5 = header_property[str](
        "Content-MD5",
        doc="""The Content-MD5 entity-header field, as defined in
        RFC 1864, is an MD5 digest of the entity-body for the purpose of
        providing an end-to-end message integrity check (MIC) of the
        entity-body. (Note: a MIC is good for detecting accidental
        modification of the entity-body in transit, but is not proof
        against malicious attacks.)""",
    )
    date = header_property(
        "Date",
        None,
        parse_date,
        http_date,
        doc="""The Date general-header field represents the date and
        time at which the message was originated, having the same
        semantics as orig-date in RFC 822.""",
    )
    expires = header_property(
        "Expires",
        None,
        parse_date,
        http_date,
        doc="""The Expires entity-header field gives the date/time after
        which the response is considered stale. A stale cache entry may
        not normally be returned by a cache.""",
    )
    last_modified = header_property(
        "Last-Modified",
        None,
        parse_date,
        http_date,
        doc="""The Last-Modified entity-header field indicates the date
        and time at which the origin server believes the variant was
        last modified.""",
    )

    @property
    def retry_after(self) -> t.Optional[datetime]:
        """The Retry-After response-header field can be used with a
        503 (Service Unavailable) response to indicate how long the
        service is expected to be unavailable to the requesting client.

        Time in seconds until expiration or date.
        """
        value = self.headers.get("retry-after")
        if value is None:
            return None
        elif value.isdigit():
            return datetime.utcnow() + timedelta(seconds=int(value))
        return parse_date(value)

    @retry_after.setter
    def retry_after(self, value: t.Optional[t.Union[datetime, int, str]]) -> None:
        if value is None:
            if "retry-after" in self.headers:
                del self.headers["retry-after"]
            return
        elif isinstance(value, datetime):
            value = http_date(value)
        else:
            value = str(value)
        self.headers["Retry-After"] = value

    vary = _set_property(
        "Vary",
        doc="""The Vary field value indicates the set of request-header
        fields that fully determines, while the response is fresh,
        whether a cache is permitted to use the response to reply to a
        subsequent request without revalidation.""",
    )
    content_language = _set_property(
        "Content-Language",
        doc="""The Content-Language entity-header field describes the
        natural language(s) of the intended audience for the enclosed
        entity. Note that this might not be equivalent to all the
        languages used within the entity-body.""",
    )
    allow = _set_property(
        "Allow",
        doc="""The Allow entity-header field lists the set of methods
        supported by the resource identified by the Request-URI. The
        purpose of this field is strictly to inform the recipient of
        valid methods associated with the resource. An Allow header
        field MUST be present in a 405 (Method Not Allowed)
        response.""",
    )

    # ETag

    @property
    def cache_control(self) -> ResponseCacheControl:
        """The Cache-Control general-header field is used to specify
        directives that MUST be obeyed by all caching mechanisms along the
        request/response chain.
        """

        def on_update(cache_control):
            if not cache_control and "cache-control" in self.headers:
                del self.headers["cache-control"]
            elif cache_control:
                self.headers["Cache-Control"] = cache_control.to_header()

        return parse_cache_control_header(
            self.headers.get("cache-control"), on_update, ResponseCacheControl
        )

    def _wrap_range_response(self, start: int, length: int) -> None:
        """Wrap existing Response in case of Range Request context."""
        if self.status_code == 206:
            self.response = _RangeWrapper(self.response, start, length)  # type: ignore

    def _is_range_request_processable(self, environ: "WSGIEnvironment") -> bool:
        """Return ``True`` if `Range` header is present and if underlying
        resource is considered unchanged when compared with `If-Range` header.
        """
        return (
            "HTTP_IF_RANGE" not in environ
            or not is_resource_modified(
                environ,
                self.headers.get("etag"),
                None,
                self.headers.get("last-modified"),
                ignore_if_range=False,
            )
        ) and "HTTP_RANGE" in environ

    def _process_range_request(
        self,
        environ: "WSGIEnvironment",
        complete_length: t.Optional[int] = None,
        accept_ranges: t.Optional[t.Union[bool, str]] = None,
    ) -> bool:
        """Handle Range Request related headers (RFC7233).  If `Accept-Ranges`
        header is valid, and Range Request is processable, we set the headers
        as described by the RFC, and wrap the underlying response in a
        RangeWrapper.

        Returns ``True`` if Range Request can be fulfilled, ``False`` otherwise.

        :raises: :class:`~werkzeug.exceptions.RequestedRangeNotSatisfiable`
                 if `Range` header could not be parsed or satisfied.
        """
        from ..exceptions import RequestedRangeNotSatisfiable

        if (
            accept_ranges is None
            or complete_length is None
            or not self._is_range_request_processable(environ)
        ):
            return False

        parsed_range = parse_range_header(environ.get("HTTP_RANGE"))

        if parsed_range is None:
            raise RequestedRangeNotSatisfiable(complete_length)

        range_tuple = parsed_range.range_for_length(complete_length)
        content_range_header = parsed_range.to_content_range_header(complete_length)

        if range_tuple is None or content_range_header is None:
            raise RequestedRangeNotSatisfiable(complete_length)

        content_length = range_tuple[1] - range_tuple[0]
        self.headers["Content-Length"] = content_length
        self.headers["Accept-Ranges"] = accept_ranges
        self.content_range = content_range_header  # type: ignore
        self.status_code = 206
        self._wrap_range_response(range_tuple[0], content_length)
        return True

    def make_conditional(
        self,
        request_or_environ: "WSGIEnvironment",
        accept_ranges: t.Union[bool, str] = False,
        complete_length: t.Optional[int] = None,
    ):
        """Make the response conditional to the request.  This method works
        best if an etag was defined for the response already.  The `add_etag`
        method can be used to do that.  If called without etag just the date
        header is set.

        This does nothing if the request method in the request or environ is
        anything but GET or HEAD.

        For optimal performance when handling range requests, it's recommended
        that your response data object implements `seekable`, `seek` and `tell`
        methods as described by :py:class:`io.IOBase`.  Objects returned by
        :meth:`~werkzeug.wsgi.wrap_file` automatically implement those methods.

        It does not remove the body of the response because that's something
        the :meth:`__call__` function does for us automatically.

        Returns self so that you can do ``return resp.make_conditional(req)``
        but modifies the object in-place.

        :param request_or_environ: a request object or WSGI environment to be
                                   used to make the response conditional
                                   against.
        :param accept_ranges: This parameter dictates the value of
                              `Accept-Ranges` header. If ``False`` (default),
                              the header is not set. If ``True``, it will be set
                              to ``"bytes"``. If ``None``, it will be set to
                              ``"none"``. If it's a string, it will use this
                              value.
        :param complete_length: Will be used only in valid Range Requests.
                                It will set `Content-Range` complete length
                                value and compute `Content-Length` real value.
                                This parameter is mandatory for successful
                                Range Requests completion.
        :raises: :class:`~werkzeug.exceptions.RequestedRangeNotSatisfiable`
                 if `Range` header could not be parsed or satisfied.
        """
        environ = _get_environ(request_or_environ)
        if environ["REQUEST_METHOD"] in ("GET", "HEAD"):
            # if the date is not in the headers, add it now.  We however
            # will not override an already existing header.  Unfortunately
            # this header will be overriden by many WSGI servers including
            # wsgiref.
            if "date" not in self.headers:
                self.headers["Date"] = http_date()
            accept_ranges = _clean_accept_ranges(accept_ranges)
            is206 = self._process_range_request(environ, complete_length, accept_ranges)
            if not is206 and not is_resource_modified(
                environ,
                self.headers.get("etag"),
                None,
                self.headers.get("last-modified"),
            ):
                if parse_etags(environ.get("HTTP_IF_MATCH")):
                    self.status_code = 412
                else:
                    self.status_code = 304
            if (
                self.automatically_set_content_length
                and "content-length" not in self.headers
            ):
                length = self.calculate_content_length()
                if length is not None:
                    self.headers["Content-Length"] = length
        return self

    def add_etag(self, overwrite: bool = False, weak: bool = False) -> None:
        """Add an etag for the current response if there is none yet.

        .. versionchanged:: 2.0
            SHA-1 is used to generate the value. MD5 may not be
            available in some environments.
        """
        if overwrite or "etag" not in self.headers:
            self.set_etag(generate_etag(self.get_data()), weak)

    def set_etag(self, etag: str, weak: bool = False) -> None:
        """Set the etag, and override the old one if there was one."""
        self.headers["ETag"] = quote_etag(etag, weak)

    def get_etag(self) -> t.Union[t.Tuple[str, bool], t.Tuple[None, None]]:
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

    @property
    def content_range(self) -> ContentRange:
        """The ``Content-Range`` header as a
        :class:`~werkzeug.datastructures.ContentRange` object. Available
        even if the header is not set.

        .. versionadded:: 0.7
        """

        def on_update(rng: ContentRange) -> None:
            if not rng:
                del self.headers["content-range"]
            else:
                self.headers["Content-Range"] = rng.to_header()

        rv = parse_content_range_header(self.headers.get("content-range"), on_update)
        # always provide a content range object to make the descriptor
        # more user friendly.  It provides an unset() method that can be
        # used to remove the header quickly.
        if rv is None:
            rv = ContentRange(None, None, None, on_update=on_update)
        return rv

    @content_range.setter
    def content_range(self, value: t.Optional[t.Union[ContentRange, str]]) -> None:
        if not value:
            del self.headers["content-range"]
        elif isinstance(value, str):
            self.headers["Content-Range"] = value
        else:
            self.headers["Content-Range"] = value.to_header()

    # Authorization

    @property
    def www_authenticate(self) -> WWWAuthenticate:
        """The ``WWW-Authenticate`` header in a parsed form."""

        def on_update(www_auth: WWWAuthenticate) -> None:
            if not www_auth and "www-authenticate" in self.headers:
                del self.headers["www-authenticate"]
            elif www_auth:
                self.headers["WWW-Authenticate"] = www_auth.to_header()

        header = self.headers.get("www-authenticate")
        return parse_www_authenticate_header(header, on_update)

    # CSP

    content_security_policy = header_property(
        "Content-Security-Policy",
        None,
        parse_csp_header,  # type: ignore
        dump_csp_header,
        doc="""The Content-Security-Policy header adds an additional layer of
        security to help detect and mitigate certain types of attacks.""",
    )
    content_security_policy_report_only = header_property(
        "Content-Security-Policy-Report-Only",
        None,
        parse_csp_header,  # type: ignore
        dump_csp_header,
        doc="""The Content-Security-Policy-Report-Only header adds a csp policy
        that is not enforced but is reported thereby helping detect
        certain types of attacks.""",
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
    def access_control_allow_credentials(self, value: t.Optional[bool]) -> None:
        if value is True:
            self.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            self.headers.pop("Access-Control-Allow-Credentials", None)

    access_control_allow_headers = header_property(
        "Access-Control-Allow-Headers",
        load_func=parse_set_header,
        dump_func=dump_header,
        doc="Which headers can be sent with the cross origin request.",
    )

    access_control_allow_methods = header_property(
        "Access-Control-Allow-Methods",
        load_func=parse_set_header,
        dump_func=dump_header,
        doc="Which methods can be used for the cross origin request.",
    )

    access_control_allow_origin = header_property[str](
        "Access-Control-Allow-Origin",
        doc="The origin or '*' for any origin that may make cross origin requests.",
    )

    access_control_expose_headers = header_property(
        "Access-Control-Expose-Headers",
        load_func=parse_set_header,
        dump_func=dump_header,
        doc="Which headers can be shared by the browser to JavaScript code.",
    )

    access_control_max_age = header_property(
        "Access-Control-Max-Age",
        load_func=int,
        dump_func=str,
        doc="The maximum age in seconds the access control settings can be cached for.",
    )


class ResponseStream:
    """A file descriptor like object used by the :class:`ResponseStreamMixin` to
    represent the body of the stream.  It directly pushes into the response
    iterable of the response object.
    """

    mode = "wb+"

    def __init__(self, response: Response):
        self.response = response
        self.closed = False

    def write(self, value: bytes) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        self.response._ensure_sequence(mutable=True)
        self.response.response.append(value)  # type: ignore
        self.response.headers.pop("Content-Length", None)
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
        return self.response.charset


class ResponseStreamMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'ResponseStreamMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Response' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
