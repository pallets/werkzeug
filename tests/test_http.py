# -*- coding: utf-8 -*-
"""
    werkzeug.http test
    ~~~~~~~~~~~~~~~~~~~

    :license: BSD license.
"""
from werkzeug.http import parse_accept_header


def test_accept_values():
    a = parse_accept_header('en-us,ru;q=0.5')
    assert a.values() == ['en-us', 'ru']
