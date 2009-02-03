=========================
Serving WSGI Applications
=========================

.. module:: werkzeug

There are many ways to serve a WSGI application.  While you're developing it,
you usually don't want to have a full-blown webserver like Apache up and
running, but instead a simple standalone one.  Because of that Werkzeug comes
with a builtin development server.

The easiest way is creating a small ``start-myproject.py`` file that runs the
application using the builtin server::

    #!/usr/bin/env python
    # -*- coding: utf-8 -*-

    from werkzeug import run_simple
    from myproject import make_app

    app = make_app(...)
    run_simple('localhost', 8080, app, use_reloader=True)

You can also pass it the `extra_files` keyword argument with a list of
additional files (like configuration files) you want to observe.

.. autofunction:: run_simple
