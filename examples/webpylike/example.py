# -*- coding: utf-8 -*-
"""
    Example application based on weblikepy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The application from th web.py tutorial.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from .webpylike import Response
from .webpylike import View
from .webpylike import WebPyApp


urls = ("/", "index", "/about", "about")


class index(View):
    def GET(self):
        return Response("Hello World")


class about(View):
    def GET(self):
        return Response("This is the about page")


app = WebPyApp(urls, globals())
