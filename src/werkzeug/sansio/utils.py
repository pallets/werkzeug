import typing as t

from .._internal import _encode_idna
from .._internal import _to_str
from ..exceptions import SecurityError
from ..urls import _URLTuple
from ..urls import uri_to_iri
from ..urls import url_join
from ..urls import url_parse
from ..urls import url_quote


def host_is_trusted(hostname: str, trusted_list: t.Iterable[str]) -> bool:
    """Check if a host matches a list of trusted names.

    :param hostname: The name to check.
    :param trusted_list: A list of valid names to match. If a name
        starts with a dot it will match all subdomains.

    .. versionadded:: 0.9
    """
    if not hostname:
        return False

    if isinstance(trusted_list, str):
        trusted_list = [trusted_list]

    def _normalize(hostname: str) -> bytes:
        if ":" in hostname:
            hostname = hostname.rsplit(":", 1)[0]

        return _encode_idna(hostname)

    try:
        hostname_bytes = _normalize(hostname)
    except UnicodeError:
        return False

    for ref in trusted_list:
        if ref.startswith("."):
            ref = ref[1:]
            suffix_match = True
        else:
            suffix_match = False

        try:
            ref_bytes = _normalize(ref)
        except UnicodeError:
            return False

        if ref_bytes == hostname_bytes:
            return True

        if suffix_match and hostname_bytes.endswith(b"." + ref_bytes):
            return True

    return False


def get_host(
    scheme: str,
    host_header: t.Optional[str],
    server: t.Optional[t.Tuple[str, t.Optional[int]]] = None,
    trusted_hosts: t.Optional[t.Iterable[str]] = None,
) -> str:
    """Return the host for the given parameters.

    This first checks the ``host_header``. If it's not present, then
    ``server`` is used. The host will only contain the port if it is
    different than the standard port for the protocol.

    Optionally, verify that the host is trusted using
    :func:`host_is_trusted` and raise a
    :exc:`~werkzeug.exceptions.SecurityError` if it is not.

    :param scheme: The protocol the request used, like ``"https"``.
    :param host_header: The ``Host`` header value.
    :param server: Address of the server. ``(host, port)``, or
        ``(path, None)`` for unix sockets.
    :param trusted_hosts: A list of trusted host names.

    :return: Host, with port if necessary.
    :raise ~werkzeug.exceptions.SecurityError: If the host is not
        trusted.
    """
    host = ""

    if host_header is not None:
        host = host_header
    elif server is not None:
        host = server[0]

        if server[1] is not None:
            host = f"{host}:{server[1]}"

    if scheme in {"http", "ws"} and host.endswith(":80"):
        host = host[:-3]
    elif scheme in {"https", "wss"} and host.endswith(":443"):
        host = host[:-4]

    if trusted_hosts is not None:
        if not host_is_trusted(host, trusted_hosts):
            raise SecurityError(f"Host {host!r} is not trusted.")

    return host


def get_current_url(
    scheme: str,
    host: str,
    root_path: t.Optional[str] = None,
    path: t.Optional[str] = None,
    query_string: t.Optional[bytes] = None,
) -> str:
    """Recreate the URL for a request. If an optional part isn't
    provided, it and subsequent parts are not included in the URL.

    The URL is an IRI, not a URI, so it may contain Unicode characters.
    Use :func:`~werkzeug.urls.iri_to_uri` to convert it to ASCII.

    :param scheme: The protocol the request used, like ``"https"``.
    :param host: The host the request was made to. See :func:`get_host`.
    :param root_path: Prefix that the application is mounted under. This
        is prepended to ``path``.
    :param path: The path part of the URL after ``root_path``.
    :param query_string: The portion of the URL after the "?".
    """
    url = [scheme, "://", host]

    if root_path is None:
        url.append("/")
        return uri_to_iri("".join(url))

    url.append(url_quote(root_path.rstrip("/")))
    url.append("/")

    if path is None:
        return uri_to_iri("".join(url))

    url.append(url_quote(path.lstrip("/")))

    if query_string:
        url.append("?")
        url.append(url_quote(query_string, safe=":&%=+$!*'(),"))

    return uri_to_iri("".join(url))


def get_content_length(
    http_content_length: t.Union[str, None] = None,
    http_transfer_encoding: t.Union[str, None] = "",
) -> t.Optional[int]:
    """Returns the content length as an integer or ``None`` if
    unavailable or chunked transfer encoding is used.

    :param http_content_length: The Content-Length HTTP header.
    :param http_transfer_encoding: The Transfer-Encoding HTTP header.

    .. versionchanged:: 2.2
        Using explicit header parameters to support ASGI.

    .. versionadded:: 0.9
    """
    if http_transfer_encoding == "chunked":
        return None

    if http_content_length is not None:
        try:
            return max(0, int(http_content_length))
        except (ValueError, TypeError):
            pass
    return None


def get_query_string(query_string: str = "") -> str:
    """Returns a sanitized query string.

    :param query_string: The (potentially unsafe) query string.

    .. versionchanged: 2.2
        Using explicit string parameter to support ASGI.

    .. versionadded:: 0.9
    """
    qs = query_string.encode("latin1")
    # QUERY_STRING really should be ascii safe but some browsers
    # will send us some unicode stuff (I am looking at you IE).
    # In that case we want to urllib quote it badly.
    return url_quote(qs, safe=":&%=+$!*'(),")


def get_path_info(
    path: str = "", charset: str = "utf-8", errors: str = "replace"
) -> str:
    """Return the decoded ``path`` unless ``charset`` is ``None``.

    :param path_info: The URL path.
    :param charset: The charset for the path info, or ``None`` if no
        decoding should be performed.
    :param errors: The decoding error handling.

    .. versionchanged: 2.2
        Using explicit string parameter to support ASGI.

    .. versionadded:: 0.9
    """
    path = path.encode("latin1")
    return _to_str(path, charset, errors, allow_none_charset=True)


def extract_path_info(
    baseurl: str,
    path_or_url: t.Union[str, _URLTuple],
    charset: str = "utf-8",
    errors: str = "werkzeug.url_quote",
    collapse_http_schemes: bool = True,
) -> t.Optional[str]:
    """Extracts the path info as a string from the baseurl and path.
    The URLs might also be IRIs.

    If the path info could not be determined, `None` is returned.

    Some examples:

    >>> extract_path_info('http://example.com/app', '/app/hello')
    '/hello'
    >>> extract_path_info('http://example.com/app',
    ...                   'https://example.com/app/hello')
    '/hello'
    >>> extract_path_info('http://example.com/app',
    ...                   'https://example.com/app/hello',
    ...                   collapse_http_schemes=False) is None
    True

    :param baseurl: a base URL or base IRI.
                    This is the root of the application.
    :param path_or_url: an absolute path from the server root, a
                        relative path (in which case it's the path info)
                        or a full URL.
    :param charset: the charset for byte data in URLs
    :param errors: the error handling on decode
    :param collapse_http_schemes: if set to `False` the algorithm does
                                  not assume that http and https on the
                                  same server point to the same
                                  resource.

    .. versionchanged: 2.2
        Using explicit baseurl string parameter to support ASGI.

    .. versionchanged:: 0.15
        The ``errors`` parameter defaults to leaving invalid bytes
        quoted instead of replacing them.

    .. versionadded:: 0.6
    """

    def _normalize_netloc(scheme: str, netloc: str) -> str:
        parts = netloc.split("@", 1)[-1].split(":", 1)
        port: t.Optional[str]

        if len(parts) == 2:
            netloc, port = parts
            if (scheme == "http" and port == "80") or (
                scheme == "https" and port == "443"
            ):
                port = None
        else:
            netloc = parts[0]
            port = None

        if port is not None:
            netloc += f":{port}"

        return netloc

    # make sure whatever we are working on is a IRI and parse it
    path = uri_to_iri(path_or_url, charset, errors)
    base_iri = uri_to_iri(baseurl, charset, errors)
    base_scheme, base_netloc, base_path = url_parse(base_iri)[:3]
    cur_scheme, cur_netloc, cur_path = url_parse(url_join(base_iri, path))[:3]

    # normalize the network location
    base_netloc = _normalize_netloc(base_scheme, base_netloc)
    cur_netloc = _normalize_netloc(cur_scheme, cur_netloc)

    # is that IRI even on a known HTTP scheme?
    if collapse_http_schemes:
        for scheme in base_scheme, cur_scheme:
            if scheme not in ("http", "https"):
                return None
    else:
        if not (base_scheme in ("http", "https") and base_scheme == cur_scheme):
            return None

    # are the netlocs compatible?
    if base_netloc != cur_netloc:
        return None

    # are we below the application path?
    base_path = base_path.rstrip("/")
    if not cur_path.startswith(base_path):
        return None

    return f"/{cur_path[len(base_path) :].lstrip('/')}"
