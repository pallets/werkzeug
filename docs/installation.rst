============
Installation
============

Werkzeug requires at least Python 2.4 to work correctly.


Installing a released version
=============================

As a Python egg (via easy_install)
----------------------------------

You can install the most recent Werkzeug version using `easy_install`_::

    sudo easy_install Werkzeug

This will install a Werkzeug egg in your Python installation's `site-packages`
directory.

From the tarball release
-------------------------

1.  Download the most recent tarball from the `download page`_.
2.  Unpack the tarball.
3.  ``sudo python setup.py install``

Note that the last command will automatically download and install
`setuptools`_ if you don't already have it installed.  This requires a working
Internet connection.

This will install Werkzeug into your Python installation's `site-packages`
directory.


Installing the development version
==================================

1.  Install `Git`_
2.  ``git clone git://github.com/mitsuhiko/werkzeug.git``
3.  ``cd werkzeug``
4.  ``ln -s werkzeug /usr/lib/python2.X/site-packages``

.. _download page: http://werkzeug.pocoo.org/download
.. _setuptools: http://peak.telecommunity.com/DevCenter/setuptools
.. _easy_install: http://peak.telecommunity.com/DevCenter/EasyInstall
.. _Git: http://git-scm.org/
