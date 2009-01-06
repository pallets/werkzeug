# -*- coding: utf-8 -*-
"""
    Example application based on weblikepy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The application from th web.py tutorial.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD.
"""
from webpylike import WebPyApp, View, Response


urls = (
    '/',        'index',
    '/about',   'about'
)


class index(View):
    def GET(self):
        return Response('Hello World')


class about(View):
    def GET(self):
        return Response('This is the about page')


app = WebPyApp(urls, globals())
