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

-   wrapper around wsgiref that works around some of the limitations
    and bugs, adds threading and fork support for test environments
    and adds an automatic reloader.

-   a flexible URL routing system with REST support.

-   fully WSGI compatible


Development Version
-------------------

The `Werkzeug tip <http://dev.pocoo.org/hg/werkzeug-main/archive/tip.zip#egg=Werkzeug-dev`
is installable via `easy_install` with ``easy_install Werkzeug==dev``.
"""
import os
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, Feature

setup(
    name='Werkzeug',
    version='0.2',
    url='http://werkzeug.pocoo.org/',
    download_url='http://werkzeug.pocoo.org/download',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='The Swiss Army knife of Python web development',
    long_description=__doc__,
    zip_safe=False,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=['werkzeug', 'werkzeug.debug'],
    package_data={
        'werkzeug.debug': ['shared/*']
    },
    features={
        'contrib': Feature('optional contribute addon modules',
            standard=True,
            packages=['werkzeug.contrib']
        )
    },
    platforms='any',
    include_package_data=True,
    extras_require={
        'plugin': ['setuptools>=0.6a2'],
        'wsgiref': ['wsgiref']
    }
)
