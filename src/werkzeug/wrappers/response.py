import typing as t

from ..utils import cached_property
from .auth import WWWAuthenticateMixin
from .base_response import BaseResponse
from .common_descriptors import CommonResponseDescriptorsMixin
from .cors import CORSResponseMixin
from .etag import ETagResponseMixin


class ResponseStream:
    """A file descriptor like object used by the :class:`ResponseStreamMixin` to
    represent the body of the stream.  It directly pushes into the response
    iterable of the response object.
    """

    mode: str = "wb+"

    def __init__(self, response: BaseResponse):
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
    """Mixin for :class:`BaseResponse` subclasses.  Classes that inherit from
    this mixin will automatically get a :attr:`stream` property that provides
    a write-only interface to the response iterable.
    """

    @cached_property
    def stream(self) -> ResponseStream:
        """The response iterable as write-only stream."""
        return ResponseStream(self)  # type: ignore


class Response(  # type: ignore
    BaseResponse,
    ETagResponseMixin,
    WWWAuthenticateMixin,
    CORSResponseMixin,
    ResponseStreamMixin,
    CommonResponseDescriptorsMixin,
):
    """Full featured response object implementing the following mixins:

    -   :class:`ETagResponseMixin` for etag and cache control handling
    -   :class:`WWWAuthenticateMixin` for HTTP authentication support
    -   :class:`~werkzeug.wrappers.cors.CORSResponseMixin` for Cross
        Origin Resource Sharing headers
    -   :class:`ResponseStreamMixin` to add support for the ``stream``
        property
    -   :class:`CommonResponseDescriptorsMixin` for various HTTP
        descriptors
    """
