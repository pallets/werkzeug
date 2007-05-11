#!/usr/bin/env python
# -*- coding: <%= FILE_ENCODING %> -*-
import sys
from <%= PACKAGE %> import make_app
from wsgiref.simple_server import make_server

if __name__ == '__main__':
    app = make_app()
    if '-d' in sys.argv or '--debug' in sys.argv:
        from werkzeug.debug import DebuggedApplication
        app = DebuggedApplication(app, evalex=True)
    srv = make_server('localhost', 5000, app)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
