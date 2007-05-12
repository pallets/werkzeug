# -*- coding: utf-8 -*-
import werkzeug
import os
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, Extension, Feature

setup(
    name = 'Werkzeug',
    version = '0.1',
    url = 'http://werkzeug.pocoo.org/',
    license = 'BSD',
    author = 'Armin Ronacher',
    author_email = 'armin.ronacher@active-4.com',
    description = 'foo',
    long_description = getdoc(pygments),
    zip_safe = True,
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: HTML'
    ],
    packages = ['werkzeug', 'werkzeug.debug'],
    platforms = 'any',
    extras_require = {'plugin': ['setuptools>=0.6a2']}
)
