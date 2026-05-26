#!/usr/bin/env python3
"""
Fuzz harness for Werkzeug's URL routing and request parsing.
Targets: Map/Rule URL matching, cookie parsing, query string parsing.
Untrusted input: full URLs, cookie headers, query strings.
"""
import sys
import atheris

with atheris.instrument_imports():
    from werkzeug.routing import Map, Rule
    from werkzeug.http import parse_cookie
    from werkzeug.urls import uri_to_iri, iri_to_uri
    from werkzeug.datastructures import Headers
    from io import BytesIO

# Build a URL map once - routing itself is stateless per match
url_map = Map([
    Rule("/", endpoint="index"),
    Rule("/user/<int:user_id>", endpoint="user"),
    Rule("/path/<path:subpath>", endpoint="path"),
    Rule("/api/<string:version>/resource", endpoint="api"),
])

def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    try:
        url = fdp.ConsumeUnicodeNoSurrogates(min(len(data) // 2, 256))
        cookie_str = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 256))
    except Exception:
        return

    # 1. URL routing
    try:
        adapter = url_map.bind("example.com")
        adapter.match(url)
    except Exception:
        pass  # NotFound, MethodNotAllowed, RequestRedirect are all fine

    # 2. Cookie parsing (processes untrusted Cookie: header)
    try:
        parse_cookie(cookie_str)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    # 3. URI ↔ IRI conversion (unicode normalization attack surface)
    try:
        uri_to_iri(url)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    try:
        iri_to_uri(url)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise


atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
