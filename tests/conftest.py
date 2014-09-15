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

try:
    from urllib2 import urlopen
except ImportError:  # pragma: no cover
    from urllib.request import urlopen


import pytest
from werkzeug import serving

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


def _get_pid_middleware(f):
    def inner(environ, start_response):
        if environ['PATH_INFO'] == '/_getpid':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [to_bytes(str(os.getpid()))]
        return f(environ, start_response)
    return inner


def _dev_server():
    sys.path.insert(0, sys.argv[1])
    import testsuite_app
    app = _get_pid_middleware(testsuite_app.app)
    serving.run_simple(hostname='localhost', application=app,
                       **testsuite_app.kwargs)

if __name__ == '__main__':
    _dev_server()


class _ServerInfo(object):
    addr = None
    url = None
    port = None


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

        def request_pid():
            for i in range(10):
                try:
                    return int(urlopen(url_base + '/_getpid').read())
                except Exception as e:  # urllib also raises socketerrors
                    print(url_base)
                    print(e)
                    time.sleep(0.1 * i)
            return False

        def preparefunc(cwd):
            args = [sys.executable, __file__, str(tmpdir)]
            return request_pid, args

        subprocess.ensure('dev_server', preparefunc, restart=True)

        def teardown():
            # Killing the process group that runs the server, not just the
            # parent process attached. xprocess is confused about Werkzeug's
            # reloader and won't help here.
            pid = request_pid()
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        request.addfinalizer(teardown)

        rv = _ServerInfo()
        rv.addr = 'localhost:{0}'.format(port)
        rv.url = url_base
        rv.port = port
        return rv

    return run_dev_server
