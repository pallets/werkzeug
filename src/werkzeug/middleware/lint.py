"""
WSGI Protocol Linter
====================

This module provides a middleware that performs sanity checks on the
behavior of the WSGI server and application. It checks that the
:pep:`3333` WSGI spec is properly implemented. It also warns on some
common HTTP errors such as non-empty responses for 304 status codes.

.. autoclass:: LintMiddleware

:copyright: 2007 Pallets
:license: BSD-3-Clause
"""
from io import BytesIO
from typing import Any
from typing import Callable
from typing import IO
from typing import List
from typing import Set
from typing import Tuple
from typing import Union
from urllib.parse import urlparse
from warnings import warn

from ..datastructures import Headers
from ..http import is_entity_header
from ..wsgi import FileWrapper
from werkzeug.types import WSGIEnvironment


class WSGIWarning(Warning):
    """Warning class for WSGI warnings."""


class HTTPWarning(Warning):
    """Warning class for HTTP warnings."""


def check_string(context: str, obj: Any, stacklevel: int = 3) -> None:
    if type(obj) is not str:
        warn(
            f"'{context}' requires strings, got '{type(obj).__name__}'",
            WSGIWarning,
        )


class InputStream:
    def __init__(self, stream: BytesIO) -> None:
        self._stream = stream

    def read(self, *args):
        if len(args) == 0:
            warn(
                "WSGI does not guarantee an EOF marker on the input stream, thus making"
                " calls to 'wsgi.input.read()' unsafe. Conforming servers may never"
                " return from this call.",
                WSGIWarning,
                stacklevel=2,
            )
        elif len(args) != 1:
            warn(
                "Too many parameters passed to 'wsgi.input.read()'.",
                WSGIWarning,
                stacklevel=2,
            )
        return self._stream.read(*args)

    def readline(self, *args):
        if len(args) == 0:
            warn(
                "Calls to 'wsgi.input.readline()' without arguments are unsafe. Use"
                " 'wsgi.input.read()' instead.",
                WSGIWarning,
                stacklevel=2,
            )
        elif len(args) == 1:
            warn(
                "'wsgi.input.readline()' was called with a size hint. WSGI does not"
                " support this, although it's available on all major servers.",
                WSGIWarning,
                stacklevel=2,
            )
        else:
            raise TypeError("Too many arguments passed to 'wsgi.input.readline()'.")
        return self._stream.readline(*args)

    def __iter__(self):
        try:
            return iter(self._stream)
        except TypeError:
            warn("'wsgi.input' is not iterable.", WSGIWarning, stacklevel=2)
            return iter(())

    def close(self):
        warn(
            "The application closed the input stream!",
            WSGIWarning,
            stacklevel=2,
        )
        self._stream.close()


class ErrorStream:
    def __init__(self, stream: IO) -> None:
        self._stream = stream

    def write(self, s):
        check_string("wsgi.error.write()", s)
        self._stream.write(s)

    def flush(self):
        self._stream.flush()

    def writelines(self, seq):
        for line in seq:
            self.write(line)

    def close(self):
        warn(
            "The application closed the error stream!",
            WSGIWarning,
            stacklevel=2,
        )
        self._stream.close()


class GuardedWrite:
    def __init__(self, write: Callable, chunks: List[Any]) -> None:
        self._write = write
        self._chunks = chunks

    def __call__(self, s):
        check_string("write()", s)
        self._write.write(s)
        self._chunks.append(len(s))


class GuardedIterator:
    def __init__(
        self,
        iterator: List[str],
        headers_set: Set[Union[int, Headers]],
        chunks: List[Any],
    ) -> None:
        self._iterator = iterator
        self._next = iter(iterator).__next__
        self.closed = False
        self.headers_set = headers_set
        self.chunks = chunks

    def __iter__(self) -> "GuardedIterator":
        return self

    def __next__(self) -> str:
        if self.closed:
            warn("Iterated over closed 'app_iter'.", WSGIWarning, stacklevel=2)

        rv = self._next()

        if not self.headers_set:
            warn(
                "The application returned before it started the response.",
                WSGIWarning,
                stacklevel=2,
            )

        check_string("application iterator items", rv)
        self.chunks.append(len(rv))
        return rv

    def close(self) -> None:
        self.closed = True

        if hasattr(self._iterator, "close"):
            self._iterator.close()  # type: ignore

        if self.headers_set:
            status_code, headers = self.headers_set
            bytes_sent = sum(self.chunks)
            content_length = headers.get("content-length", type=int)  # type: ignore

            if status_code == 304:
                for key, _value in headers:  # type: ignore
                    key = key.lower()
                    if (
                        key
                        not in (
                            "expires",
                            "content-location",
                        )
                        and is_entity_header(key)
                    ):
                        warn(
                            f"Entity header {key!r} found in 304 response.",
                            HTTPWarning,
                        )
                if bytes_sent:
                    warn("304 responses must not have a body.", HTTPWarning)
            elif 100 <= status_code < 200 or status_code == 204:  # type: ignore
                if content_length != 0:
                    warn(
                        f"{status_code} responses must have an empty content length.",
                        HTTPWarning,
                    )
                if bytes_sent:
                    warn(
                        f"{status_code} responses must not have a body.",
                        HTTPWarning,
                    )
            elif content_length is not None and content_length != bytes_sent:
                warn(
                    "Content-Length and the number of bytes sent to the client do not"
                    " match.",
                    WSGIWarning,
                )

    def __del__(self) -> None:
        if not self.closed:
            try:
                warn(
                    "Iterator was garbage collected before it was closed.",
                    WSGIWarning,
                )
            except Exception:
                pass


class LintMiddleware:
    """Warns about common errors in the WSGI and HTTP behavior of the
    server and wrapped application. Some of the issues it checks are:

    -   invalid status codes
    -   non-bytes sent to the WSGI server
    -   strings returned from the WSGI application
    -   non-empty conditional responses
    -   unquoted etags
    -   relative URLs in the Location header
    -   unsafe calls to wsgi.input
    -   unclosed iterators

    Error information is emitted using the :mod:`warnings` module.

    :param app: The WSGI application to wrap.

    .. code-block:: python

        from werkzeug.middleware.lint import LintMiddleware
        app = LintMiddleware(app)
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    def check_environ(
        self,
        environ: WSGIEnvironment,
    ) -> None:
        if type(environ) is not dict:
            warn(
                "WSGI environment is not a standard Python dict.",
                WSGIWarning,
                stacklevel=4,
            )
        for key in (
            "REQUEST_METHOD",
            "SERVER_NAME",
            "SERVER_PORT",
            "wsgi.version",
            "wsgi.input",
            "wsgi.errors",
            "wsgi.multithread",
            "wsgi.multiprocess",
            "wsgi.run_once",
        ):
            if key not in environ:
                warn(
                    f"Required environment key {key!r} not found",
                    WSGIWarning,
                    stacklevel=3,
                )
        if environ["wsgi.version"] != (1, 0):
            warn("Environ is not a WSGI 1.0 environ.", WSGIWarning, stacklevel=3)

        script_name = environ.get("SCRIPT_NAME", "")
        path_info = environ.get("PATH_INFO", "")

        if script_name and script_name[0] != "/":
            warn(
                f"'SCRIPT_NAME' does not start with a slash: {script_name!r}",
                WSGIWarning,
                stacklevel=3,
            )

        if path_info and path_info[0] != "/":
            warn(
                f"'PATH_INFO' does not start with a slash: {path_info!r}",
                WSGIWarning,
                stacklevel=3,
            )

    def check_start_response(
        self,
        status: str,
        headers: Union[List[Tuple[str, str]], Tuple[Tuple[str, str]], List[str]],
        exc_info: None,
    ) -> Tuple[int, Headers]:
        check_string("status", status)
        status_code = status.split(None, 1)[0]

        if len(status_code) != 3 or not status_code.isdigit():
            warn(WSGIWarning("Status code must be three digits"), stacklevel=3)

        if len(status) < 4 or status[3] != " ":
            warn(
                WSGIWarning(
                    f"Invalid value for status {status!r}.  Valid "
                    "status strings are three digits, a space "
                    "and a status explanation"
                ),
                stacklevel=3,
            )

        status_code = int(status_code)

        if status_code < 100:
            warn(WSGIWarning("status code < 100 detected"), stacklevel=3)

        if type(headers) is not list:
            warn(WSGIWarning("header list is not a list"), stacklevel=3)

        for item in headers:
            if type(item) is not tuple or len(item) != 2:
                warn(
                    WSGIWarning("Headers must tuple 2-item tuples"),
                    stacklevel=3,
                )
            name, value = item  # type: ignore
            if type(name) is not str or type(value) is not str:
                warn(WSGIWarning("header items must be strings"), stacklevel=3)
            if name.lower() == "status":
                warn(
                    WSGIWarning(
                        "The status header is not supported due to "
                        "conflicts with the CGI spec."
                    ),
                    stacklevel=3,
                )

        if exc_info is not None and not isinstance(exc_info, tuple):
            warn(WSGIWarning("invalid value for exc_info"), stacklevel=3)

        headers = Headers(headers)
        self.check_headers(headers)

        return status_code, headers

    def check_headers(self, headers: Headers) -> None:
        etag = headers.get("etag")

        if etag is not None:
            if etag.startswith(("W/", "w/")):
                if etag.startswith("w/"):
                    warn(
                        HTTPWarning("weak etag indicator should be upcase."),
                        stacklevel=4,
                    )

                etag = etag[2:]

            if not (etag[:1] == etag[-1:] == '"'):
                warn(HTTPWarning("unquoted etag emitted."), stacklevel=4)

        location = headers.get("location")

        if location is not None:
            if not urlparse(location).netloc:
                warn(
                    HTTPWarning("absolute URLs required for location header"),
                    stacklevel=4,
                )

    def check_iterator(self, app_iter: List[str]) -> None:
        if isinstance(app_iter, str):
            warn(
                "The application returned a string. The response will send one"
                " character at a time to the client, which will kill performance."
                " Return a list or iterable instead.",
                WSGIWarning,
                stacklevel=3,
            )

    def __call__(self, *args, **kwargs) -> GuardedIterator:
        if len(args) != 2:
            warn("A WSGI app takes two arguments.", WSGIWarning, stacklevel=2)

        if kwargs:
            warn(
                "A WSGI app does not take keyword arguments.",
                WSGIWarning,
                stacklevel=2,
            )

        environ, start_response = args

        self.check_environ(environ)
        environ["wsgi.input"] = InputStream(environ["wsgi.input"])
        environ["wsgi.errors"] = ErrorStream(environ["wsgi.errors"])

        # Hook our own file wrapper in so that applications will always
        # iterate to the end and we can check the content length.
        environ["wsgi.file_wrapper"] = FileWrapper

        headers_set: List[Any] = []
        chunks: List[Any] = []

        def checking_start_response(*args, **kwargs):
            if len(args) not in (2, 3):
                warn(
                    f"Invalid number of arguments: {len(args)}, expected 2 or 3.",
                    WSGIWarning,
                    stacklevel=2,
                )

            if kwargs:
                warn(
                    "'start_response' does not take keyword arguments.",
                    WSGIWarning,
                )

            status, headers = args[:2]

            if len(args) == 3:
                exc_info = args[2]
            else:
                exc_info = None

            headers_set[:] = self.check_start_response(status, headers, exc_info)
            return GuardedWrite(start_response(status, headers, exc_info), chunks)

        app_iter = self.app(environ, checking_start_response)
        self.check_iterator(app_iter)
        return GuardedIterator(app_iter, headers_set, chunks)  # type: ignore
