# Werkzeug Fuzz Harnesses

This directory contains [atheris](https://github.com/google/atheris) fuzz harnesses
for Werkzeug's security-sensitive HTTP parsing code.

## Harnesses

| File | Target | Attack Surface |
|------|--------|---------------|
| `fuzz_http_headers.py` | `werkzeug.http` header parsers | `parse_options_header`, `parse_cache_control_header`, `parse_range_header`, `parse_date`, etc. |
| `fuzz_url_routing.py` | URL routing, cookie parsing, URI conversion | `Map.match`, `parse_cookie`, `uri_to_iri`, `iri_to_uri` |
| `fuzz_multipart_decoder.py` | `sansio.MultipartDecoder` state machine | Raw multipart body bytes — boundary detection, header parsing, state transitions |

## Running

```bash
# Install dependencies
pip install atheris werkzeug

# Run a harness (e.g. 60 seconds)
python fuzz/fuzz_multipart_decoder.py -max_total_time=60

# Run with a seed corpus
python fuzz/fuzz_http_headers.py corpus/ -max_total_time=60
```

## Why These Targets

- **HTTP header parsers** process untrusted `Content-Type`, `Cache-Control`, `Range`,
  and `Content-Range` headers directly from HTTP requests
- **URL routing** processes untrusted URL paths and cookie strings
- **MultipartDecoder** is a streaming state machine processing untrusted request bodies
  (file uploads) — historically a high-risk area across web frameworks

Bugs in these paths could cause unhandled exceptions that crash WSGI servers,
ReDoS that stalls worker threads, or parser confusion exploitable for smuggling attacks.
