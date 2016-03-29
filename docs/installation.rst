============
Installation
============

Werkzeug requires at least Python 2.6 to work correctly.  If you do need
to support an older version you can download an older version of Werkzeug
though we strongly recommend against that.  Werkzeug currently has
experimental support for Python 3.  For more information about the
Python 3 support see :ref:`python3`.


Installing a released version
=============================

As a Python egg (via easy_install or pip)
-----------------------------------------

You can install the most recent Werkzeug version using `easy_install`_::

    easy_install Werkzeug

Alternatively you can also use pip::

    pip install Werkzeug

Either way we strongly recommend using these tools in combination with
:ref:`virtualenv`.

This will install a Werkzeug egg in your Python installation's `site-packages`
directory.

From the tarball release
-------------------------

1.  Download the most recent tarball from the `download page`_.
2.  Unpack the tarball.
3.  ``python setup.py install``

Note that the last command will automatically download and install
`setuptools`_ if you don't already have it installed.  This requires a working
Internet connection.

This will install Werkzeug into your Python installation's `site-packages`
directory.


Installing the development version
==================================

1.  Install `Git`_
2.  ``git clone git://github.com/pallets/werkzeug.git``
3.  ``cd werkzeug``
4.  ``pip install --editable .``

.. _virtualenv:

virtualenv
==========

Virtualenv is probably what you want to use during development, and in
production too if you have shell access there.

What problem does virtualenv solve?  If you like Python as I do,
chances are you want to use it for other projects besides Werkzeug-based
web applications.  But the more projects you have, the more likely it is
that you will be working with different versions of Python itself, or at
least different versions of Python libraries.  Let's face it; quite often
libraries break backwards compatibility, and it's unlikely that any serious
application will have zero dependencies.  So what do you do if two or more
of your projects have conflicting dependencies?

Virtualenv to the rescue!  It basically enables multiple side-by-side
installations of Python, one for each project.  It doesn't actually
install separate copies of Python, but it does provide a clever way
to keep different project environments isolated.

So let's see how virtualenv works!

If you are on Mac OS X or Linux, chances are that one of the following two
commands will work for you::

    $ sudo easy_install virtualenv

or even better::

    $ sudo pip install virtualenv

One of these will probably install virtualenv on your system.  Maybe it's
even in your package manager.  If you use Ubuntu, try::

    $ sudo apt-get install python-virtualenv

If you are on Windows and don't have the `easy_install` command, you must
install it first.  Once you have it installed, run the same commands as
above, but without the `sudo` prefix.

Once you have virtualenv installed, just fire up a shell and create
your own environment.  I usually create a project folder and an `env`
folder within::

    $ mkdir myproject
    $ cd myproject
    $ virtualenv env
    New python executable in env/bin/python
    Installing setuptools............done.

Now, whenever you want to work on a project, you only have to activate
the corresponding environment.  On OS X and Linux, do the following::

    $ . env/bin/activate

(Note the space between the dot and the script name.  The dot means that
this script should run in the context of the current shell.  If this command
does not work in your shell, try replacing the dot with ``source``)

If you are a Windows user, the following command is for you::

    $ env\scripts\activate

Either way, you should now be using your virtualenv (see how the prompt of
your shell has changed to show the virtualenv).

Now you can just enter the following command to get Werkzeug activated in
your virtualenv::

    $ pip install Werkzeug

A few seconds later you are good to go.

.. _download page: https://pypi.python.org/pypi/Werkzeug
.. _setuptools: http://peak.telecommunity.com/DevCenter/setuptools
.. _easy_install: http://peak.telecommunity.com/DevCenter/EasyInstall
.. _Git: http://git-scm.org/
