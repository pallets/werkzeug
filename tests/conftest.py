import http.client
import json
import os
import socket
import ssl
import sys
from itertools import count
from pathlib import Path

import pytest
from xprocess import ProcessStarter

from werkzeug.utils import cached_property

run_path = str(Path(__file__).parent / "live_apps" / "run.py")


def get_free_port():
    gen_port = count(49152)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    while True:
        port = next(gen_port)

        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue

        s.close()
        return port


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


class DevServerClient:
    def __init__(self, kwargs):
        host = kwargs.get("hostname", "127.0.0.1")

        if not host.startswith("unix"):
            port = kwargs.get("port")

            if port is None:
                kwargs["port"] = port = get_free_port()

            scheme = "https" if "ssl_context" in kwargs else "http"
            self.addr = f"{host}:{port}"
            self.url = f"{scheme}://{self.addr}"
        else:
            self.addr = host[7:]  # strip "unix://"
            self.url = host

        self.log = None

    def tail_log(self, path):
        self.log = open(path)
        self.log.read()

    def connect(self, **kwargs):
        protocol = self.url.partition(":")[0]

        if protocol == "https":
            if "context" not in kwargs:
                kwargs["context"] = ssl.SSLContext()

            return http.client.HTTPSConnection(self.addr, **kwargs)

        if protocol == "unix":
            return UnixSocketHTTPConnection(self.addr, **kwargs)

        return http.client.HTTPConnection(self.addr, **kwargs)

    def request(self, path="", **kwargs):
        kwargs.setdefault("method", "GET")
        kwargs.setdefault("url", path)
        conn = self.connect()
        conn.request(**kwargs)

        with conn.getresponse() as response:
            response.data = response.read()

        conn.close()

        if response.headers.get("Content-Type", "").startswith("application/json"):
            response.json = json.loads(response.data)
        else:
            response.json = None

        return response

    def wait_for_log(self, start):
        while True:
            for line in self.log:
                if line.startswith(start):
                    return

    def wait_for_reload(self):
        self.wait_for_log(" * Restarting with ")


@pytest.fixture()
def dev_server(xprocess, request, tmp_path):
    """A function that will start a dev server in an external process
    and return a client for interacting with the server.
    """

    def start_dev_server(name="standard", **kwargs):
        client = DevServerClient(kwargs)

        class Starter(ProcessStarter):
            args = [sys.executable, run_path, name, json.dumps(kwargs)]
            # Extend the existing env, otherwise Windows and CI fails.
            # Modules will be imported from tmp_path for the reloader.
            # Unbuffered output so the logs update immediately.
            env = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONUNBUFFERED": "1"}

            @cached_property
            def pattern(self):
                client.request("/ensure")
                return "GET /ensure"

        # Each test that uses the fixture will have a different log.
        xp_name = f"dev_server-{request.node.name}"
        _, log_path = xprocess.ensure(xp_name, Starter, restart=True)
        client.tail_log(log_path)

        @request.addfinalizer
        def close():
            xprocess.getinfo(xp_name).terminate()
            client.log.close()

        return client

    return start_dev_server


@pytest.fixture()
def standard_app(dev_server):
    """Equivalent to ``dev_server("standard")``."""
    return dev_server()
