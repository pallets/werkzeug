# -*- coding: utf-8 -*-
"""
    tests.conftest
    ~~~~~~~~~~~~~~

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from __future__ import print_function

import logging
import os
import platform
import signal
import subprocess
import sys
import textwrap
import time
from itertools import count

import pytest

from werkzeug import serving
from werkzeug._compat import to_bytes
from werkzeug.urls import url_quote
from werkzeug.utils import cached_property

try:
    __import__("pytest_xprocess")
except ImportError:

    @pytest.fixture(scope="session")
    def xprocess():
        pytest.skip("pytest-xprocess not installed.")


port_generator = count(13220)


def _patch_reloader_loop():
    def f(x):
        print("reloader loop finished")
        # Need to flush for some reason even though xprocess opens the
        # subprocess' stdout in unbuffered mode.
        # flush=True makes the test fail on py2, so flush manually
        sys.stdout.flush()
        return time.sleep(x)

    import werkzeug._reloader

    werkzeug._reloader.ReloaderLoop._sleep = staticmethod(f)


pid_logger = logging.getLogger("get_pid_middleware")
pid_logger.setLevel(logging.INFO)
pid_handler = logging.StreamHandler(sys.stdout)
pid_logger.addHandler(pid_handler)


def _get_pid_middleware(f):
    def inner(environ, start_response):
        if environ["PATH_INFO"] == "/_getpid":
            start_response("200 OK", [("Content-Type", "text/plain")])
            pid_logger.info("pid=%s", os.getpid())
            return [to_bytes(str(os.getpid()))]
        return f(environ, start_response)

    return inner


def _dev_server():
    _patch_reloader_loop()
    sys.path.insert(0, sys.argv[1])
    import testsuite_app

    app = _get_pid_middleware(testsuite_app.app)
    serving.run_simple(application=app, **testsuite_app.kwargs)


class _ServerInfo(object):
    xprocess = None
    addr = None
    url = None
    port = None
    last_pid = None

    def __init__(self, xprocess, addr, url, port):
        self.xprocess = xprocess
        self.addr = addr
        self.url = url
        self.port = port

    @cached_property
    def logfile(self):
        return self.xprocess.getinfo("dev_server").logpath.open()

    def request_pid(self):
        if self.url.startswith("http+unix://"):
            from requests_unixsocket import get as rget
        else:
            from requests import get as rget

        for i in range(10):
            time.sleep(0.1 * i)
            try:
                response = rget(self.url + "/_getpid", verify=False)
                self.last_pid = int(response.text)
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


@pytest.fixture
def dev_server(tmpdir, xprocess, request, monkeypatch):
    """Run werkzeug.serving.run_simple in its own process.

    :param application: String for the module that will be created. The module
        must have a global ``app`` object, a ``kwargs`` dict is also available
        whose values will be passed to ``run_simple``.
    """

    def run_dev_server(application):
        app_pkg = tmpdir.mkdir("testsuite_app")
        appfile = app_pkg.join("__init__.py")
        port = next(port_generator)
        appfile.write(
            "\n\n".join(
                (
                    "kwargs = {{'hostname': 'localhost', 'port': {port:d}}}".format(
                        port=port
                    ),
                    textwrap.dedent(application),
                )
            )
        )

        monkeypatch.delitem(sys.modules, "testsuite_app", raising=False)
        monkeypatch.syspath_prepend(str(tmpdir))
        import testsuite_app

        hostname = testsuite_app.kwargs["hostname"]
        port = testsuite_app.kwargs["port"]
        addr = "{}:{}".format(hostname, port)

        if hostname.startswith("unix://"):
            addr = hostname.split("unix://", 1)[1]
            requests_url = "http+unix://" + url_quote(addr, safe="")
        elif testsuite_app.kwargs.get("ssl_context", None):
            requests_url = "https://localhost:{0}".format(port)
        else:
            requests_url = "http://localhost:{0}".format(port)

        info = _ServerInfo(xprocess, addr, requests_url, port)

        from xprocess import ProcessStarter

        class Starter(ProcessStarter):
            args = [sys.executable, __file__, str(tmpdir)]

            @property
            def pattern(self):
                return "pid=%s" % info.request_pid()

        xprocess.ensure("dev_server", Starter, restart=True)

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


if __name__ == "__main__":
    _dev_server()
