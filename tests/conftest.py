import json
import os
import platform
import signal
import subprocess
import sys
import time
from http import client as http_client
from itertools import count

import pytest

from werkzeug.urls import url_quote
from werkzeug.utils import cached_property

try:
    __import__("pytest_xprocess")
except ImportError:

    @pytest.fixture(scope="session")
    def xprocess():
        pytest.skip("pytest-xprocess not installed.")


port_generator = count(13220)


class _ServerInfo:
    xprocess = None
    addr = None
    url = None
    port = None
    conn = None
    last_pid = None

    def __init__(self, xprocess, addr, url, port):
        self.xprocess = xprocess
        self.addr = addr
        self.url = url
        self.port = port
        self.conn = None
        if self.url.split(":")[0] == "https":
            self.conn = http_client.HTTPSConnection(self.addr)
        elif self.url.split(":")[0] == "http":
            self.conn = http_client.HTTPConnection(self.addr)

    @cached_property
    def logfile(self):
        return self.xprocess.getinfo(f"dev_server_{self.port}").logpath.open()

    def request_pid(self):
        for i in range(10):
            time.sleep(0.1 * i)
            try:
                if self.url.startswith("http+unix://"):
                    self.last_pid = self._get_unix_server_pid()
                else:
                    response = self.get(f"{self.url}/_getpid")
                    self.last_pid = int(response.read().decode())
                return self.last_pid
            except Exception as e:  # urllib also raises socketerrors
                print(self.url)
                print(e)

    def wait_for_reloader(self):
        old_pid = self.last_pid
        for i in range(20):
            time.sleep(0.1 * i)
            new_pid = self.request_pid()
            if not new_pid:
                raise RuntimeError("Server is down.")
            if new_pid != old_pid:
                return
        raise RuntimeError("Server did not reload.")

    def wait_for_reloader_loop(self):
        for i in range(20):
            time.sleep(0.1 * i)
            line = self.logfile.readline()
            if "reloader loop finished" in line:
                return

    def get(self, url, headers={}):  # noqa: B006
        if not self.conn:
            raise NotImplementedError("Not implemented for unix servers")
        self.conn.request("GET", url, headers=headers)
        return self.conn.getresponse()

    def _get_unix_server_pid(self):
        import socket
        from urllib.parse import urlparse, unquote

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        socket_path = unquote(urlparse(self.url).netloc)
        sock.connect(socket_path)
        sock.sendall(b"GET /_getpid HTTP/1.1 \n\n")
        data = sock.recv(2048)
        sock.close()
        return int(data.decode().split()[-1])


@pytest.fixture(scope="module")
def standard_app(dev_server):
    return dev_server("standard_app")


@pytest.fixture(scope="module")
def chunked_app(dev_server):
    return dev_server("chunked_app")


@pytest.fixture(scope="module")
def monkeymodule(request):
    # module scoped monkeypatch
    # from: https://github.com/pytest-dev/pytest/issues/363
    from _pytest.monkeypatch import MonkeyPatch

    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope="module")
def dev_server(tmpdir_factory, xprocess, request, monkeymodule):
    """Run werkzeug.serving.run_simple in its own process.

    :param application: String for the module that will be created. The module
        must have a global ``app`` object, a ``kwargs`` dict is also available
        whose values will be passed to ``run_simple``.
    """

    def run_dev_server(application, **kwargs):
        port = next(port_generator)
        app_kwargs = {"hostname": "localhost", "port": port}
        app_kwargs.update(dict(kwargs))

        monkeymodule.delitem(sys.modules, "test_apps", raising=False)
        import test_apps

        hostname = app_kwargs["hostname"]
        port = app_kwargs["port"]
        addr = f"{hostname}:{port}"

        if hostname.startswith("unix://"):
            addr = hostname.split("unix://", 1)[1]
            requests_url = f"http+unix://{url_quote(addr, safe='')}"
        elif app_kwargs.get("ssl_context", None):
            requests_url = f"https://localhost:{port}"
        else:
            requests_url = f"http://localhost:{port}"

        info = _ServerInfo(xprocess, addr, requests_url, port)

        from xprocess import ProcessStarter

        class Starter(ProcessStarter):
            args = [
                sys.executable,
                os.path.join(os.getcwd(), "tests/run_dev_server.py"),
                test_apps,
                str(tmpdir_factory.getbasetemp()),
                application,
                json.dumps(app_kwargs),
            ]

            @property
            def pattern(self):
                return f"pid={info.request_pid()}"

        xprocess.ensure(f"dev_server_{port}", Starter, restart=True)

        @request.addfinalizer
        def teardown():
            # Killing the process group that runs the server, not just the
            # parent process attached. xprocess is confused about Werkzeug's
            # reloader and won't help here.
            pid = info.request_pid()
            if not pid:
                return
            if platform.system() == "Windows":
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(pid)])
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)

        return info

    return run_dev_server
