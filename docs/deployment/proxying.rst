=============
HTTP Proxying
=============

Many people prefer using a standalone Python HTTP server and proxying that
server via nginx, Apache etc.

A very stable Python server is CherryPy.  This part of the documentation
shows you how to combine your WSGI application with the CherryPy WSGI
server and how to configure the webserver for proxying.


Creating a `.py` server
=======================

To run your application you need a `start-server.py` file that starts up
the WSGI Server.

It looks something along these lines::

    from cherrypy import wsgiserver
    from yourapplication import make_app
    server = wsgiserver.CherryPyWSGIServer(('localhost', 8080), make_app())
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

If you now start the file the server will listen on `localhost:8080`.  Keep
in mind that WSGI applications behave slightly different for proxied setups.
If you have not developed your application for proxying in mind, you can
apply the :class:`~werkzeug.middleware.proxy_fix.ProxyFix` middleware.


Configuring nginx
=================

As an example we show here how to configure nginx to proxy to the server.

The basic nginx configuration looks like this::

    location / {
        proxy_set_header        Host $host;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass              http://127.0.0.1:8080;
        proxy_redirect          default;
    }

Since Nginx doesn't start your server for you, you have to do it by yourself.  You
can either write an `init.d` script for that or execute it inside a screen
session::

    $ screen
    $ python start-server.py
