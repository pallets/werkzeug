# -*- coding: utf-8 -*-
"""
Werkzeug
========

Werkzeug started as simple collection of various utilities for WSGI
applications and has become one of the most advanced WSGI utility
modules.  It includes a powerful debugger, full featured request and
response objects, HTTP utilities to handle entity tags, cache control
headers, HTTP dates, cookie handling, file uploads, a powerful URL
routing system and a bunch of community contributed addon modules.

Werkzeug is unicode aware and doesn't enforce a specific template
engine, database adapter or anything else.  It doesn't even enforce
a specific way of handling requests and leaves all that up to the
developer. It's most useful for end user applications which should work
on as many server environments as possible (such as blogs, wikis,
bulletin boards, etc.).

Details and example applications are available on the
`Werkzeug website <http://werkzeug.pocoo.org/>`_.


Features
--------

-   unicode awareness

-   request and response objects

-   various utility functions for dealing with HTTP headers such as
    `Accept` and `Cache-Control` headers.

-   thread local objects with proper cleanup at request end

-   an interactive debugger

-   A simple WSGI server with support for threading and forking
    with an automatic reloader.

-   a flexible URL routing system with REST support.

-   fully WSGI compatible


Development Version
-------------------

The Werkzeug development version can be installed by cloning the git
repository from `github`_::

    git clone git@github.com:mitsuhiko/werkzeug.git

.. _github: http://github.com/mitsuhiko/werkzeug
"""
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='Werkzeug',
    version='0.8.3',
    url='http://werkzeug.pocoo.org/',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='The Swiss Army knife of Python web development',
    long_description=__doc__,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=['werkzeug', 'werkzeug.debug', 'werkzeug.contrib',
              'werkzeug.testsuite', 'werkzeug.testsuite.contrib'],
    include_package_data=True,
    test_suite='werkzeug.testsuite.suite',
    zip_safe=False,
    platforms='any'
)
