from __future__ import annotations

from urllib.parse import quote

# RFC 3986 characters, excluding &= which appear in query string
_always_safe_rfc3986 = "$!'()*+,;"


def _quote(
    string: str | bytes,
    safe: str = "/",
    encoding: str | None = None,
    errors: str | None = None,
) -> str:
    safe = f"{_always_safe_rfc3986}{safe}"
    return quote(string, safe=safe, encoding=encoding, errors=errors)
