#!/usr/bin/env python
"""
    Manage Cup Of Tee
    ~~~~~~~~~~~~~~~~~

    Manage the cup of tee application.

    :copyright: 2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from cupoftee import make_app
from werkzeug import script


action_runserver = script.make_runserver(make_app)

script.run()
