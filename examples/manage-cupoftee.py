#!/usr/bin/env python
"""
    Manage Cup Of Tee
    ~~~~~~~~~~~~~~~~~

    Manage the cup of tee application.

    :copyright: 2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import script


def make_app():
    from cupoftee import make_app
    return make_app('/tmp/cupoftee.db')
action_runserver = script.make_runserver(make_app)

script.run()
