===
CGI
===

If all other deployment methods do not work, CGI will work for sure.  CGI
is supported by all major servers but usually has a less-than-optimal
performance.

This is also the way you can use a Werkzeug application on Google's
`AppEngine`_, there however the execution does happen in a CGI-like
environment.  The application's performance is unaffected because of that.

.. _AppEngine: https://cloud.google.com/appengine/

Creating a `.cgi` file
======================

First you need to create the CGI application file.  Let's call it
`yourapplication.cgi`::

    #!/usr/bin/python
    from wsgiref.handlers import CGIHandler
    from yourapplication import make_app

    application = make_app()
    CGIHandler().run(application)

Server Setup
============

Usually there are two ways to configure the server.  Either just copy the
`.cgi` into a `cgi-bin` (and use `mod_rewrite` or something similar to
rewrite the URL) or let the server point to the file directly.

In Apache for example you can put something like this into the config:

.. sourcecode:: apache

    ScriptAlias /app /path/to/the/application.cgi

For more information consult the documentation of your webserver.
