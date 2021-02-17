import typing as t

from .._internal import _encode_idna
from ..exceptions import SecurityError


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
