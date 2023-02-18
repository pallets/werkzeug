from __future__ import annotations

import typing as t
from urllib.parse import quote
from urllib.parse import urlencode

from werkzeug.datastructures import iter_multi_items

# RFC 3986 characters, excluding &= which appear in query string
_rfc3986 = "$!'()*+,;"


def _quote(
    string: str | bytes,
    safe: str = "/",
    encoding: str | None = None,
    errors: str | None = None,
) -> str:
    return quote(string, safe=f"{_rfc3986}{safe}", encoding=encoding, errors=errors)


def _urlencode(
    query: t.Mapping[str, str] | t.Iterable[tuple[str, str]], encoding: str = "utf-8"
):
    items = [x for x in iter_multi_items(query) if x[1] is not None]
    return urlencode(items, safe=f"{_rfc3986}/", encoding=encoding)
