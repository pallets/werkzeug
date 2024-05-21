import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path

import ephemeral_port_reserve
import pytest

run_path = str(Path(__file__).parent / "live_apps" / "run.py")


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
                kwargs["port"] = port = ephemeral_port_reserve.reserve(host)

            scheme = "https" if "ssl_context" in kwargs else "http"
            self.addr = f"{host}:{port}"
            self.url = f"{scheme}://{self.addr}"
        else:
            self.addr = host[7:]  # strip "unix://"
            self.url = host

        self.proc = None

    def get_logs(self):
        logs = ""
        try:
            for line in self.proc.communicate(timeout=2):
                logs += str(line)
        except subprocess.TimeoutExpired:
            pass
        return logs

    def connect(self, **kwargs):
        protocol = self.url.partition(":")[0]

        if protocol == "https":
            if "context" not in kwargs:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                kwargs["context"] = context

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
        data = bytearray()
        start = bytes(start, encoding='utf8')
        while True:
            if self.proc is not None:
                data += self.proc.stdout.read1()
                if start in data:
                    return

    def wait_for_reload(self):
        self.wait_for_log(" * Restarting with ")

    def wait_for_server(self):
        while True:
            try:
                response = self.request("/ensure")
                if response.status == 200:
                    return
            except ConnectionRefusedError or ConnectionResetError:
                pass


@pytest.fixture()
def dev_server(request, tmp_path):
    """A function that will start a dev server in an external process
    and return a client for interacting with the server.
    """

    def start_dev_server(name="standard", **kwargs):
        client = DevServerClient(kwargs)

        args = [sys.executable, run_path, name, json.dumps(kwargs)]
        # Extend the existing env, otherwise Windows and CI fails.
        # Modules will be imported from tmp_path for the reloader.
        # Unbuffered output so the logs update immediately.
        env_info = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONUNBUFFERED": "1"}

        proc = subprocess.Popen(
            args, env=env_info, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        client = DevServerClient(kwargs)
        client.proc = proc
        client.wait_for_server()

        @request.addfinalizer
        def close():
            client.proc.kill()
            try:
                _, _ = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        return client

    return start_dev_server


@pytest.fixture()
def standard_app(dev_server):
    """Equivalent to ``dev_server("standard")``."""
    return dev_server()
