import typing as t

from .._internal import _encode_idna
from ..exceptions import SecurityError
from ..urls import uri_to_iri
from ..urls import url_quote


def host_is_trusted(hostname: str, trusted_list: t.Iterable[str]) -> bool:
    """Checks if a host is trusted against a list.  This also takes care
    of port normalization.
    .. versionadded:: 0.9
    :param hostname: the hostname to check
    :param trusted_list: a list of hostnames to check against.  If a
    hostname starts with a dot it will match against all subdomains as
    well.
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

    :param scheme: The request scheme.
    :param host_header: The Host header value or None if not present.
    :param server: Either a two-item iterable of (host, port), where
    host is the listening address for this server, and port is the
    integer listening port, or (path, None) where path is that of the
    unix socket, or None if no server knowledge.
    :param trusted_hosts: A list of trusted hosts.

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
            raise SecurityError(f'Host "{host}" is not trusted')
    return host


def get_current_url(
    scheme: str,
    host: str,
    path: str,
    root_path: str,
    query_string: bytes,
    root_only: bool = False,
    strip_querystring: bool = False,
    host_only: bool = False,
) -> str:
    """A handy helper function that recreates the full URL as IRI for the
    current request or parts of it.  Here's an example:

    >>> get_current_url("http", "localhost", "/script", "", "param=foo")
    'http://localhost/script/?param=foo'
    >>> get_current_url("http", "localhost", "/script", "", "param=foo", root_only=True)
    'http://localhost/script/'
    >>> get_current_url("http", "localhost", "/script", "", "param=foo", host_only=True)
    'http://localhost/'
    >>> get_current_url("http", "localhost", "/script", "", "param=foo", strip_querystring=True)
    'http://localhost/script/'

    Note that the string returned might contain unicode characters as the
    representation is an IRI not an URI.  If you need an ASCII only
    representation you can use the :func:`~werkzeug.urls.iri_to_uri`
    function:

    >>> from werkzeug.urls import iri_to_uri
    >>> iri_to_uri(get_current_url("http", "localhost", "/script", "", "param=foo"))
    'http://localhost/script/?param=foo'

    :param scheme: the HTTP Scheme.
    :param host: the requested host.
    :param path: the request target path.
    :param root_path: The SCRIPT_NAME (wsgi) or root_path (asgi).
    :param query_string: the request target querystring.
    :param root_only: set `True` if you only want the root URL.
    :param strip_querystring: set to `True` if you don't want the querystring.
    :param host_only: set to `True` if the host URL should be returned.
    :param trusted_hosts: a list of trusted hosts, see :func:`host_is_trusted`
                          for more information.
    """
    url = [scheme, "://", host]
    if host_only:
        return uri_to_iri(f"{''.join(url)}/")
    url.append(url_quote(root_path).rstrip("/"))
    url.append("/")
    if not root_only:
        url.append(url_quote(path).lstrip("/"))
        if not strip_querystring:
            url.append("?")
            url.append(url_quote(query_string, safe=":&%=+$!*'(),"))
    return uri_to_iri("".join(url))
