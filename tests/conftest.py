from __future__ import annotations

import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from contextlib import closing
from contextlib import ExitStack
from pathlib import Path

import ephemeral_port_reserve
import pytest


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # Raises FileNotFoundError if the server hasn't started yet.
        self.sock.connect(self.host)


class DevServerClient:
    def __init__(self, app_name="standard", *, tmp_path, **server_kwargs):
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
        self._log_write = None
        self._log_read = None
        self._proc = None

    def __enter__(self):
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._proc.terminate()
        self._proc.wait()
        self._proc = None
        self._log_read.close()
        self._log_read = None
        self._log_write.close()
        self._log_write = None

    def connect(self, **kwargs):
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

    def request(self, url: str, **kwargs):
        kwargs.setdefault("method", "GET")
        kwargs["url"] = url

        with closing(self.connect()) as conn:
            conn.request(**kwargs)

            with conn.getresponse() as response:
                response.data = response.read()

        if response.headers.get("Content-Type", "").startswith("application/json"):
            response.json = json.loads(response.data)
        else:
            response.json = None

        return response

    def wait_ready(self):
        while True:
            try:
                self.request("/ensure")
                return
            # ConnectionRefusedError for http, FileNotFoundError for unix
            except (ConnectionRefusedError, FileNotFoundError):
                time.sleep(0.1)

    def read_log(self) -> str:
        return self._log_read.read()

    def wait_for_log(self, value):
        while True:
            for line in self._log_read:
                if value in line:
                    return

            time.sleep(0.1)

    def wait_for_reload(self):
        self.wait_for_log("Restarting with")
        self.wait_ready()


@pytest.fixture()
def dev_server(tmp_path):
    """A function that will start a dev server in a subprocess and return a
    client for interacting with the server.
    """
    exit_stack = ExitStack()

    def start_dev_server(name="standard", **kwargs):
        client = DevServerClient(name, tmp_path=tmp_path, **kwargs)
        exit_stack.enter_context(client)
        return client

    with exit_stack:
        yield start_dev_server


@pytest.fixture()
def standard_app(dev_server):
    """Equivalent to ``dev_server("standard")``."""
    return dev_server()
