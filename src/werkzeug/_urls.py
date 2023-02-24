from __future__ import annotations

import re
import typing as t
from urllib.parse import quote
from urllib.parse import unquote
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


def _make_unquote_part(
    name: str, chars: str
) -> t.Callable[[str, str | None, str | None], str]:
    """Create a function that unquotes all percent encoded characters except those
    given. This allows working with unquoted characters if possible while not changing
    the meaning of a given part of a URL.
    """
    choices = "|".join(f"{ord(c):02X}" for c in sorted(chars))
    pattern = re.compile(f"((?:%(?:{choices}))+)", re.I)

    def _unquote_partial(
        value: str, encoding: str | None = None, errors: str | None = None
    ) -> str:
        parts = iter(pattern.split(value))
        out = []

        for part in parts:
            out.append(unquote(part, encoding, errors))
            out.append(next(parts, ""))

        return "".join(out)

    _unquote_partial.__name__ = f"_unquote_{name}"
    return _unquote_partial


# characters that should remain quoted in URL parts
# based on https://url.spec.whatwg.org/#percent-encoded-bytes
# always keep all controls, space, and % quoted
_always_unsafe = bytes((*range(0x21), 0x25, 0x7F)).decode()
_unquote_fragment = _make_unquote_part("fragment", _always_unsafe)
_unquote_query = _make_unquote_part("query", _always_unsafe + "&;=+#")
_unquote_path = _make_unquote_part("path", _always_unsafe + "/;?#")
_unquote_user = _make_unquote_part("user", _always_unsafe + ":@/?#")
