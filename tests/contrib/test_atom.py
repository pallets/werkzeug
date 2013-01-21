# -*- coding: utf-8 -*-
"""
    tests.atom
    ~~~~~~~~~~

    Tests the cache system

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import datetime

from werkzeug.contrib.atom import format_iso8601


def test_format_iso8601():
    # naive datetime should be treated as utc
    dt = datetime.datetime(2014, 8, 31, 2, 5, 6)
    assert format_iso8601(dt) == '2014-08-31T02:05:06Z'

    # tz-aware datetime
    dt = datetime.datetime(2014, 8, 31, 11, 5, 6, tzinfo=KST())
    assert format_iso8601(dt) == '2014-08-31T11:05:06+09:00'


class KST(datetime.tzinfo):
    """KST implementation for test_format_iso8601()."""

    def utcoffset(self, dt):
        return datetime.timedelta(hours=9)

    def tzname(self, dt):
        return 'KST'

    def dst(self, dt):
        return datetime.timedelta(0)
