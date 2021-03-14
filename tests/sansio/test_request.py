import typing as t

import pytest

from werkzeug.datastructures import Headers
from werkzeug.sansio.request import Request


@pytest.mark.parametrize(
    "headers, expected",
    [
        (Headers({"Transfer-Encoding": "chunked", "Content-Length": "6"}), None),
        (Headers({"Transfer-Encoding": "something", "Content-Length": "6"}), 6),
        (Headers({"Content-Length": "6"}), 6),
        (Headers(), None),
    ],
)
def test_content_length(headers: Headers, expected: t.Optional[int]) -> None:
    req = Request("POST", "http", None, "", "", b"", headers, None)
    assert req.content_length == expected
