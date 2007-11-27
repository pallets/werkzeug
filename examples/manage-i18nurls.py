#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage i18nurls
    ~~~~~~~~~~~~~~~

    Manage the i18n url example application.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
from i18nurls import make_app
from werkzeug import script

action_runserver = script.make_runserver(make_app)
action_shell = script.make_shell(lambda: {})

if __name__ == '__main__':
    script.run()
