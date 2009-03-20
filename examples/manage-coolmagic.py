#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage Coolmagic
    ~~~~~~~~~~~~~~~~

    Manage the coolmagic example application.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from coolmagic import make_app
from werkzeug import script

action_runserver = script.make_runserver(make_app, use_reloader=True)
action_shell = script.make_shell(lambda: {})

if __name__ == '__main__':
    script.run()
