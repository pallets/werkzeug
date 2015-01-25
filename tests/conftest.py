# -*- coding: utf-8 -*-
"""
    tests.conftest
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement

import os
import signal
import sys
import textwrap
import time

import requests
import pytest

from werkzeug import serving
from werkzeug.utils import cached_property
from werkzeug._compat import to_bytes


try:
    __import__('pytest_xprocess')
except ImportError:
    @pytest.fixture
    def subprocess():
        pytest.skip('pytest-xprocess not installed.')
else:
    @pytest.fixture
    def subprocess(xprocess):
        return xprocess


def _patch_reloader_loop():
    def f(x):
        print('reloader loop finished')
        return time.sleep(x)

    import werkzeug._reloader
    werkzeug._reloader.ReloaderLoop._sleep = staticmethod(f)


def _get_pid_middleware(f):
    def inner(environ, start_response):
        if environ['PATH_INFO'] == '/_getpid':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [to_bytes(str(os.getpid()))]
        return f(environ, start_response)
    return inner


def _dev_server():
    _patch_reloader_loop()
    sys.path.insert(0, sys.argv[1])
    import testsuite_app
    app = _get_pid_middleware(testsuite_app.app)
    serving.run_simple(hostname='localhost', application=app,
                       **testsuite_app.kwargs)

if __name__ == '__main__':
    _dev_server()


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
        return self.xprocess.getinfo('dev_server').logpath.open()

    def request_pid(self):
        for i in range(20):
            time.sleep(0.1 * i)
            try:
                self.last_pid = int(requests.get(self.url + '/_getpid',
                                                 verify=False).text)
                return self.last_pid
            except Exception as e:  # urllib also raises socketerrors
                print(self.url)
                print(e)
        return False

    def wait_for_reloader(self):
        old_pid = self.last_pid
        for i in range(20):
            time.sleep(0.1 * i)
            new_pid = self.request_pid()
            if not new_pid:
                raise RuntimeError('Server is down.')
            if self.request_pid() != old_pid:
                return
        raise RuntimeError('Server did not reload.')

    def wait_for_reloader_loop(self):
        for i in range(20):
            time.sleep(0.1 * i)
            line = self.logfile.readline()
            if 'reloader loop finished' in line:
                return


@pytest.fixture
def dev_server(tmpdir, subprocess, request, monkeypatch):
    '''Run werkzeug.serving.run_simple in its own process.

    :param application: String for the module that will be created. The module
        must have a global ``app`` object, a ``kwargs`` dict is also available
        whose values will be passed to ``run_simple``.
    '''
    def run_dev_server(application):
        app_pkg = tmpdir.mkdir('testsuite_app')
        appfile = app_pkg.join('__init__.py')
        appfile.write('\n\n'.join((
            'kwargs = dict(port=5001)',
            textwrap.dedent(application)
        )))

        monkeypatch.delitem(sys.modules, 'testsuite_app', raising=False)
        monkeypatch.syspath_prepend(str(tmpdir))
        import testsuite_app
        port = testsuite_app.kwargs['port']

        if testsuite_app.kwargs.get('ssl_context', None):
            url_base = 'https://localhost:{0}'.format(port)
        else:
            url_base = 'http://localhost:{0}'.format(port)

        info = _ServerInfo(
            subprocess,
            'localhost:{0}'.format(port),
            url_base,
            port
        )

        def preparefunc(cwd):
            args = [sys.executable, __file__, str(tmpdir)]
            return info.request_pid, args

        subprocess.ensure('dev_server', preparefunc, restart=True)

        def teardown():
            # Killing the process group that runs the server, not just the
            # parent process attached. xprocess is confused about Werkzeug's
            # reloader and won't help here.
            pid = info.last_pid
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        request.addfinalizer(teardown)

        return info

    return run_dev_server
