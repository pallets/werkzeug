#!/usr/bin/env python
from cupoftee import make_app
from werkzeug import script


action_runserver = script.make_runserver(make_app)

script.run()
