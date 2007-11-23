#!/usr/bin/env python
# -*- coding: utf-8 -*-
from werkzeug.serving import run_simple
from coolmagic import make_app

# development configuration
config = {
    'debug':            True,
    'evalex':           True,
    'auto_reload':      True
}

if __name__ == '__main__':
    run_simple('localhost', 5000, make_app(config), config['auto_reload'])
