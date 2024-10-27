from __future__ import annotations

import collections.abc as cabc
import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import typing as t
from contextlib import closing
from contextlib import ExitStack
from pathlib import Path
from types import TracebackType

import ephemeral_port_reserve
import pytest

if t.TYPE_CHECKING:
    import typing_extensions as te


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # Raises FileNotFoundError if the server hasn't started yet.
        self.sock.connect(self.host)


# Used to annotate the ``DevServerClient.request`` return value.
class DataHTTPResponse(http.client.HTTPResponse):
    data: bytes
    json: t.Any


class DevServerClient:
    """Manage a live dev server process and make requests to it. Must be used
    as a context manager.

    If ``hostname`` starts with ``unix://``, the server listens to a unix socket
    file instead of a TCP socket.

    If ``port`` is not given, a random port is reserved for use by the server,
    to allow multiple servers to run simultaneously.

    If ``ssl_context`` is given, the server listens with TLS enabled. It can be
    the special value ``custom`` to generate and pass a context to
    ``run_simple``, as opposed to ``adhoc`` which tells ``run_simple`` to
    generate the context.

    :param app_name: The name of the app from the ``live_apps`` folder to load.
    :param tmp_path: The current test's temporary directory. The server process
        sets the working dir here, it is added to the Python path, the log file
        is written here, and for unix connections the socket is opened here.
    :param server_kwargs: Arguments to pass to ``live_apps/run.py`` to control
        how ``run_simple`` is called in the subprocess.
    """

    scheme: str
    """One of ``http``, ``https``, or ``unix``. Set based on ``ssl_context`` or
    ``hostname``.
    """
    addr: str
    """The host and port."""
    url: str
    """The scheme, host, and port."""

    def __init__(
        self, app_name: str = "standard", *, tmp_path: Path, **server_kwargs: t.Any
    ) -> None:
        host = server_kwargs.get("hostname", "127.0.0.1")

        if not host.startswith("unix://"):
            port = server_kwargs.get("port")

            if port is None:
                server_kwargs["port"] = port = ephemeral_port_reserve.reserve(host)

            self.scheme = "https" if "ssl_context" in server_kwargs else "http"
            self.addr = f"{host}:{port}"
            self.url = f"{self.scheme}://{self.addr}"
        else:
            self.scheme = "unix"
            self.addr = host[7:]  # strip "unix://"
            self.url = host

        self._app_name = app_name
        self._server_kwargs = server_kwargs
        self._tmp_path = tmp_path
        self._log_write: t.IO[bytes] | None = None
        self._log_read: t.IO[str] | None = None
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> te.Self:
        """Start the server process and wait for it to be ready."""
        log_path = self._tmp_path / "log.txt"
        self._log_write = open(log_path, "wb")
        self._log_read = open(log_path, encoding="utf8", errors="surrogateescape")
        tmp_dir = os.fspath(self._tmp_path)
        self._proc = subprocess.Popen(
            [
                sys.executable,
                os.fspath(Path(__file__).parent / "live_apps/run.py"),
                self._app_name,
                json.dumps(self._server_kwargs),
            ],
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": tmp_dir},
            cwd=tmp_dir,
            close_fds=True,
            stdout=self._log_write,
            stderr=subprocess.STDOUT,
        )
        self.wait_ready()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        """Clean up the server process."""
        assert self._proc is not None
        self._proc.terminate()
        self._proc.wait()
        self._proc = None
        assert self._log_read is not None
        self._log_read.close()
        self._log_read = None
        assert self._log_write is not None
        self._log_write.close()
        self._log_write = None

    def connect(self, **kwargs: t.Any) -> http.client.HTTPConnection:
        """Create a connection to the server, without sending a request.
        Useful if a test requires lower level methods to try something that
        ``HTTPClient.request`` will not do.

        If the server's scheme is HTTPS and the TLS ``context`` argument is not
        given, a default permissive context is used.

        :param kwargs: Arguments to :class:`http.client.HTTPConnection`.
        """
        if self.scheme == "https":
            if "context" not in kwargs:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                kwargs["context"] = context

            return http.client.HTTPSConnection(self.addr, **kwargs)

        if self.scheme == "unix":
            return UnixSocketHTTPConnection(self.addr, **kwargs)

        return http.client.HTTPConnection(self.addr, **kwargs)

    def request(self, url: str = "", **kwargs: t.Any) -> DataHTTPResponse:
        """Open a connection and make a request to the server, returning the
        response.

        The response object ``data`` parameter has the result of
        ``response.read()``. If the response has a ``application/json`` content
         type, the ``json`` parameter is populated with ``json.loads(data)``.

        :param url: URL to put in the request line.
        :param kwargs: Arguments to :meth:`http.client.HTTPConnection.request`.
        """
        kwargs.setdefault("method", "GET")
        kwargs["url"] = url
        response: DataHTTPResponse

        with closing(self.connect()) as conn:
            conn.request(**kwargs)

            with conn.getresponse() as response:  # type: ignore[assignment]
                response.data = response.read()

        if response.headers.get("Content-Type", "").startswith("application/json"):
            response.json = json.loads(response.data)
        else:
            response.json = None

        return response

    def wait_ready(self) -> None:
        """Wait until a request to ``/ensure`` is successful, indicating the
        server has started and is listening.
        """
        while True:
            try:
                self.request("/ensure")
                return
            # ConnectionRefusedError for http, FileNotFoundError for unix
            except (ConnectionRefusedError, FileNotFoundError):
                time.sleep(0.1)

    def read_log(self) -> str:
        """Read from the current position to the current end of the log."""
        assert self._log_read is not None
        return self._log_read.read()

    def wait_for_log(self, value: str) -> None:
        """Wait until a line in the log contains the given string.

        :param value: The string to search for.
        """
        assert self._log_read is not None

        while True:
            for line in self._log_read:
                if value in line:
                    return

            time.sleep(0.1)

    def wait_for_reload(self) -> None:
        """Wait until the server logs that it is restarting, then wait for it to
        be ready.
        """
        self.wait_for_log("Restarting with")
        self.wait_ready()


class StartDevServer(t.Protocol):
    def __call__(self, name: str = "standard", **kwargs: t.Any) -> DevServerClient: ...


@pytest.fixture()
def dev_server(tmp_path: Path) -> cabc.Iterator[StartDevServer]:
    """A function that will start a dev server in a subprocess and return a
    client for interacting with the server.
    """
    exit_stack = ExitStack()

    def start_dev_server(name: str = "standard", **kwargs: t.Any) -> DevServerClient:
        client = DevServerClient(name, tmp_path=tmp_path, **kwargs)
        exit_stack.enter_context(client)  # type: ignore[arg-type]
        return client

    with exit_stack:
        yield start_dev_server


@pytest.fixture()
def standard_app(dev_server: t.Callable[..., DevServerClient]) -> DevServerClient:
    """Equivalent to ``dev_server("standard")``."""
    return dev_server()
