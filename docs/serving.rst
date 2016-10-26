=========================
Serving WSGI Applications
=========================

.. module:: werkzeug.serving

There are many ways to serve a WSGI application.  While you're developing it,
you usually don't want to have a full-blown webserver like Apache up and
running, but instead a simple standalone one.  Because of that Werkzeug comes
with a builtin development server.

The easiest way is creating a small ``start-myproject.py`` file that runs the
application using the builtin server::

    #!/usr/bin/env python
    # -*- coding: utf-8 -*-

    from werkzeug.serving import run_simple
    from myproject import make_app

    app = make_app(...)
    run_simple('localhost', 8080, app, use_reloader=True)

You can also pass it the `extra_files` keyword argument with a list of
additional files (like configuration files) you want to observe.

.. autofunction:: run_simple

.. autofunction:: is_running_from_reloader

.. autofunction:: make_ssl_devcert

.. admonition:: Information

   The development server is not intended to be used on production systems.
   It was designed especially for development purposes and performs poorly
   under high load.  For deployment setups have a look at the
   :ref:`deployment` pages.

.. _reloader:

Reloader
--------

.. versionchanged:: 0.10

The Werkzeug reloader constantly monitors modules and paths of your web
application, and restarts the server if any of the observed files change.

Since version 0.10, there are two backends the reloader supports: ``stat`` and
``watchdog``.

- The default ``stat`` backend simply checks the ``mtime`` of all files in a
  regular interval. This is sufficient for most cases, however, it is known to
  drain a laptop's battery.

- The ``watchdog`` backend uses filesystem events, and is much faster than
  ``stat``. It requires the `watchdog <https://pypi.python.org/pypi/watchdog>`_
  module to be installed. The recommended way to achieve this is to add
  ``Werkzeug[watchdog]`` to your requirements file.

If ``watchdog`` is installed and available it will automatically be used
instead of the builtin ``stat`` reloader.

To switch between the backends you can use the `reloader_type` parameter of the
:func:`run_simple` function. ``'stat'`` sets it to the default stat based
polling and ``'watchdog'`` forces it to the watchdog backend.

.. note::

    Some edge cases, like modules that failed to import correctly, are not
    handled by the stat reloader for performance reasons. The watchdog reloader
    monitors such files too.

Colored Logging
---------------
Werkzeug is able to color the output of request logs when ran from a terminal, just install the `termcolor
<https://pypi.python.org/pypi/termcolor>`_ package. Windows users need to install `colorama
<https://pypi.python.org/pypi/colorama>`_ in addition to termcolor for this to work. 

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

Shutting Down The Server
------------------------

.. versionadded:: 0.7

Starting with Werkzeug 0.7 the development server provides a way to shut
down the server after a request.  This currently only works with Python
2.6 and later and will only work with the development server.  To initiate
the shutdown you have to call a function named
``'werkzeug.server.shutdown'`` in the WSGI environment::

    def shutdown_server(environ):
        if not 'werkzeug.server.shutdown' in environ:
            raise RuntimeError('Not running the development server')
        environ['werkzeug.server.shutdown']()

Troubleshooting
---------------

On operating systems that support ipv6 and have it configured such as modern
Linux systems, OS X 10.4 or higher as well as Windows Vista some browsers can
be painfully slow if accessing your local server.  The reason for this is that
sometimes "localhost" is configured to be available on both ipv4 and ipv6 sockets
and some browsers will try to access ipv6 first and then ipv4.

At the current time the integrated webserver does not support ipv6 and ipv4 at
the same time and for better portability ipv4 is the default.

If you notice that the web browser takes ages to load the page there are two ways
around this issue.  If you don't need ipv6 support you can disable the ipv6 entry
in the `hosts file`_ by removing this line::

    ::1             localhost

Alternatively you can also disable ipv6 support in your browser.  For example
if Firefox shows this behavior you can disable it by going to ``about:config``
and disabling the `network.dns.disableIPv6` key.  This however is not
recommended as of Werkzeug 0.6.1!

Starting with Werkzeug 0.6.1, the server will now switch between ipv4 and
ipv6 based on your operating system's configuration.  This means if that
you disabled ipv6 support in your browser but your operating system is
preferring ipv6, you will be unable to connect to your server.  In that
situation, you can either remove the localhost entry for ``::1`` or
explicitly bind the hostname to an ipv4 address (`127.0.0.1`)

.. _hosts file: http://en.wikipedia.org/wiki/Hosts_file

SSL
---

.. versionadded:: 0.6

The builtin server supports SSL for testing purposes.  If an SSL context is
provided it will be used.  That means a server can either run in HTTP or HTTPS
mode, but not both.

Quickstart
``````````

The easiest way to do SSL based development with Werkzeug is by using it
to generate an SSL certificate and private key and storing that somewhere
and to then put it there.  For the certificate you need to provide the
name of your server on generation or a `CN`.

1.  Generate an SSL key and store it somewhere:

    >>> from werkzeug.serving import make_ssl_devcert
    >>> make_ssl_devcert('/path/to/the/key', host='localhost')
    ('/path/to/the/key.crt', '/path/to/the/key.key')

2.  Now this tuple can be passed as ``ssl_context`` to the
    :func:`run_simple` method::

        run_simple('localhost', 4000, application,
                   ssl_context=('/path/to/the/key.crt',
                                '/path/to/the/key.key'))

You will have to acknowledge the certificate in your browser once then.

Loading Contexts by Hand
````````````````````````

In Python 2.7.9 and 3+ you also have the option to use a ``ssl.SSLContext``
object instead of a simple tuple. This way you have better control over the SSL
behavior of Werkzeug's builtin server::

    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain('ssl.cert', 'ssl.key')
    run_simple('localhost', 4000, application, ssl_context=ctx)


.. versionchanged 0.10:: ``OpenSSL`` contexts are not supported anymore.

Generating Certificates
```````````````````````

A key and certificate can be created in advance using the openssl tool
instead of the :func:`make_ssl_devcert`.  This requires that you have
the `openssl` command installed on your system::

    $ openssl genrsa 1024 > ssl.key
    $ openssl req -new -x509 -nodes -sha1 -days 365 -key ssl.key > ssl.cert

Adhoc Certificates
``````````````````

The easiest way to enable SSL is to start the server in adhoc-mode.  In
that case Werkzeug will generate an SSL certificate for you::

    run_simple('localhost', 4000, application,
               ssl_context='adhoc')

The downside of this of course is that you will have to acknowledge the
certificate each time the server is reloaded.  Adhoc certificates are
discouraged because modern browsers do a bad job at supporting them for
security reasons.

This feature requires the pyOpenSSL library to be installed.
