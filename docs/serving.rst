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

Virtual Hosts
-------------

Many web applications utilize multiple subdomains.  This can be a bit tricky
to simulate locally.  Fortunately there is the `hosts file`_ that can be used
to assign the local computer multiple names.

This allows you to call your local computer `yourapplication.local` and
`api.yourapplication.local` (or anything else) in addition to `localhost`.

You can find the hosts file on the following location:

    =============== ==============================================
    Windows         ``%SystemRoot%\system32\drivers\etc\hosts``
    Linux / OS X    ``/etc/hosts``
    =============== ==============================================

You can open the file with your favorite text editor and add a new name after
`localhost`::

    127.0.0.1       localhost yourapplication.local api.yourapplication.local

Save the changes and after a while you should be able to access the
development server on these host names as well.  You can use the
:ref:`routing` system to dispatch between different hosts or parse
:attr:`request.host` yourself.

.. _hosts file: http://en.wikipedia.org/wiki/Hosts_file
