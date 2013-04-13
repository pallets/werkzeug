#!/usr/bin/env python
import os
import tempfile
from werkzeug import script

def make_app():
    from shorty.application import Shorty
    filename = os.path.join(tempfile.gettempdir(), "shorty.db")
    return Shorty('sqlite:///{0}'.format(filename))

def make_shell():
    from shorty import models, utils
    application = make_app()
    return locals()

action_runserver = script.make_runserver(make_app, use_reloader=True)
action_shell = script.make_shell(make_shell)
action_initdb = lambda: make_app().init_database()

script.run()
