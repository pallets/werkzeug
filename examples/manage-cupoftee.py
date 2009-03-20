#!/usr/bin/env python
"""
    Manage Cup Of Tee
    ~~~~~~~~~~~~~~~~~

    Manage the cup of tee application.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import script


def make_app():
    from cupoftee import make_app
    return make_app('/tmp/cupoftee.db')
action_runserver = script.make_runserver(make_app)

script.run()
