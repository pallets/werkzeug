===================
`mod_wsgi` (Apache)
===================

If you are using the `Apache`_ webserver you should consider using `mod_wsgi`_.

.. _Apache: https://httpd.apache.org/

Installing `mod_wsgi`
=====================

If you don't have `mod_wsgi` installed yet you have to either install it using
a package manager or compile it yourself.

The mod_wsgi `installation instructions`_ cover installation instructions for
source installations on UNIX systems.

If you are using ubuntu / debian you can apt-get it and activate it as follows::

    # apt-get install libapache2-mod-wsgi

On FreeBSD install `mod_wsgi` by compiling the `www/mod_wsgi` port or by using
pkg_add::

    # pkg_add -r mod_wsgi

If you are using pkgsrc you can install `mod_wsgi` by compiling the
`www/ap2-wsgi` package.

If you encounter segfaulting child processes after the first apache reload you
can safely ignore them.  Just restart the server.

Creating a `.wsgi` file
=======================

To run your application you need a `yourapplication.wsgi` file.  This file
contains the code `mod_wsgi` is executing on startup to get the application
object.  The object called `application` in that file is then used as
application.

For most applications the following file should be sufficient::

    from yourapplication import make_app
    application = make_app()

If you don't have a factory function for application creation but a singleton
instance you can directly import that one as `application`.

Store that file somewhere where you will find it again (eg:
`/var/www/yourapplication`) and make sure that `yourapplication` and all
the libraries that are in use are on the python load path.  If you don't
want to install it system wide consider using a `virtual python`_ instance.

Configuring Apache
==================

The last thing you have to do is to create an Apache configuration file for
your application.  In this example we are telling `mod_wsgi` to execute the
application under a different user for security reasons:

.. sourcecode:: apache

    <VirtualHost *>
        ServerName example.com

        WSGIDaemonProcess yourapplication user=user1 group=group1 processes=2 threads=5
        WSGIScriptAlias / /var/www/yourapplication/yourapplication.wsgi

        <Directory /var/www/yourapplication>
            WSGIProcessGroup yourapplication
            WSGIApplicationGroup %{GLOBAL}
            Order deny,allow
            Allow from all
        </Directory>
    </VirtualHost>

.. _mod_wsgi: https://modwsgi.readthedocs.io/en/develop/
.. _installation instructions: https://modwsgi.readthedocs.io/en/develop/installation.html
.. _virtual python: https://pypi.org/project/virtualenv/
