import logging
import threading

import pytest

import werkzeug._internal as _internal
from werkzeug._internal import _plain_int
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


def test_wrapper_internals():
    req = Request.from_values(data={"foo": "bar"}, method="POST")
    req._load_form_data()
    assert req.form.to_dict() == {"foo": "bar"}

    # second call does not break
    req._load_form_data()
    assert req.form.to_dict() == {"foo": "bar"}

    # check reprs
    assert repr(req) == "<Request 'http://localhost/' [POST]>"
    resp = Response()
    assert repr(resp) == "<Response 0 bytes [200 OK]>"
    resp.set_data("Hello World!")
    assert repr(resp) == "<Response 12 bytes [200 OK]>"
    resp.response = iter(["Test"])
    assert repr(resp) == "<Response streamed [200 OK]>"

    response = Response(["Hällo Wörld"])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" in headers

    response = Response(["Hällo Wörld".encode()])
    headers = response.get_wsgi_headers(create_environ())
    assert "Content-Length" in headers


@pytest.mark.parametrize(
    ("value", "base", "expect"),
    [
        ("123", 10, 123),
        ("-123", 10, -123),
        ("1_23", 10, None),
        ("+123", 10, None),
        ("𝟙𝟚𝟛", 10, None),
        ("7B", 10, None),
        ("7B", 16, 123),
        ("-7B", 16, -123),
        ("7b", 16, 123),
        ("0x7B", 16, None),
        (" 123", 10, 123),
        ("\t123", 10, 123),
        ("\N{PARAGRAPH SEPARATOR}123", 10, None),
    ],
)
def test_plain_int(value: str, base: int, expect: int | None) -> None:
    if expect is None:
        with pytest.raises(ValueError):
            _plain_int(value, base)
    else:
        assert _plain_int(value, base) == expect


def test_log_installs_exactly_one_handler_under_concurrency():
    """The lazy logger setup in _log() must not run more than once.

    Both `_logger is None` and `_has_level_handler()` are check-then-act, so
    threads emitting their first werkzeug log line at the same moment could
    each add a handler, after which every log line is emitted once per extra
    handler.
    """
    logger = logging.getLogger("werkzeug")
    root = logging.getLogger()
    original = (logger.handlers[:], logger.level, root.handlers[:], _internal._logger)

    n_threads = 4
    go = threading.Event()

    try:
        for _ in range(50):
            # _has_level_handler() walks up to the root logger, and under
            # pytest the root already has a capture handler -- which would
            # make werkzeug correctly decline to add its own. Clear it so the
            # branch under test actually runs.
            root.handlers.clear()
            logger.handlers.clear()
            logger.setLevel(logging.NOTSET)
            _internal._logger = None

            def worker() -> None:
                # An Event rather than a Barrier, so a runner that can only
                # give us some of the threads still runs.
                go.wait()
                _internal._log("info", "hello")

            threads = []
            for _ in range(n_threads):
                thread = threading.Thread(target=worker)
                try:
                    thread.start()
                except RuntimeError:
                    break
                threads.append(thread)

            if len(threads) < 2:
                go.set()
                for thread in threads:
                    thread.join()
                pytest.skip("could not start enough threads to test for the race")

            go.set()
            for thread in threads:
                thread.join()
            go.clear()

            assert len(logger.handlers) == 1
    finally:
        go.set()
        logger.handlers[:], logger.level, root.handlers[:], _internal._logger = original
