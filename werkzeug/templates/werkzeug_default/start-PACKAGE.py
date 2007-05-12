#!/usr/bin/env werkzeug-serve
# -*- coding: <%= FILE_ENCODING %> -*-
from <%= PACKAGE %> import make_app
application = make_app()
