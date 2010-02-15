# -*- coding: utf-8 -*-
from datetime import datetime
from werkzeug import _internal as internal


def test_date_to_unix():
    """Date to UNIX timestamp conversions."""
    assert internal._date_to_unix(datetime(1970, 1, 1)) == 0
    assert internal._date_to_unix(datetime(1970, 1, 1, 1, 0, 0)) == 3600
    assert internal._date_to_unix(datetime(1970, 1, 1, 1, 1, 1)) == 3661
    x = datetime(2010, 2, 15, 16, 15, 39)
    assert internal._date_to_unix(x) == 1266250539
