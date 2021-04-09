"""
    tests.urls
    ~~~~~~~~~~

    URL helper tests.

    :copyright: 2020 Pallets
    :license: BSD-3-Clause
"""
import pytest

from werkzeug import useragents


@pytest.mark.parametrize(
    ("user_agent", "platform", "browser", "version", "language"),
    (
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36 Edge/13.10586",  # noqa B950
            "windows",
            "edge",
            "13.10586",
            None,
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36 Edg/81.0.416.68",  # noqa B950
            "windows",
            "edge",
            "81.0.416.68",
            None,
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4123.0 Safari/537.36 Edg/84.0.499.0",  # noqa B950
            "windows",
            "edge",
            "84.0.499.0",
            None,
        ),
        (
            "Mozilla/5.0 (Linux; Android 9; motorola one macro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.111 Mobile Safari/537.36",  # noqa B950
            "android",
            "chrome",
            "84.0.4147.111",
            None,
        ),
    ),
)
def test_edge_browsers(user_agent, platform, browser, version, language):
    with pytest.deprecated_call():
        parsed = useragents.UserAgentParser()(user_agent)

    assert parsed == (platform, browser, version, language)
