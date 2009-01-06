#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage web.py like application
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A small example application that is built after the web.py tutorial.  We
    even use regular expression based dispatching.  The original code can be
    found on the `webpy.org webpage`__ in the tutorial section.

    __ http://webpy.org/tutorial2.en

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'webpylike'))
from example import app
from werkzeug import script

action_runserver = script.make_runserver(lambda: app)
action_shell = script.make_shell(lambda: {})

if __name__ == '__main__':
    script.run()
