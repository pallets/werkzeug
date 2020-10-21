import json
import logging
import os
import sys
import time

from werkzeug import serving
from werkzeug._internal import _to_bytes


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
            return [_to_bytes(str(os.getpid()))]
        return f(environ, start_response)

    return inner


def _dev_server():
    _patch_reloader_loop()
    sys.path.insert(0, sys.argv[1])
    sys.path.insert(0, sys.argv[2])
    import test_apps

    app = _get_pid_middleware(getattr(test_apps, sys.argv[3], None))
    kwargs = json.loads(sys.argv[4])
    if sys.argv[3] == "stdlib_ssl_app":
        kwargs.update(test_apps.ssl_kwargs)
    serving.run_simple(application=app, **kwargs)


if __name__ == "__main__":
    _dev_server()
