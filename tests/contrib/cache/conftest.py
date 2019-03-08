import os

import pytest

# build the path to the uwsgi marker file
# when running in tox, this will be relative to the tox env
filename = os.path.join(os.environ.get("TOX_ENVTMPDIR", ""), "test_uwsgi_failed")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """``uwsgi --pyrun`` doesn't pass on the exit code when ``pytest`` fails,
    so Tox thinks the tests passed. For UWSGI tests, create a file to mark what
    tests fail. The uwsgi Tox env has a command to read this file and exit
    appropriately.
    """
    outcome = yield
    report = outcome.get_result()

    if item.cls.__name__ != "TestUWSGICache":
        return

    if report.failed:
        with open(filename, "a") as f:
            f.write(item.name + "\n")
