#!/usr/bin/env python
from wsgiref.simple_server import make_server
from werkzeug.debug import DebuggedApplication
from i18nurls import application

application = DebuggedApplication(application(), evalex=True)
srv = make_server('localhost', 5000, application)
srv.serve_forever()
