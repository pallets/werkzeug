# -*- coding: utf-8 -*-
import werkzeug
import os
import ez_setup
from inspect import getdoc
ez_setup.use_setuptools()

from setuptools import setup, Feature

setup(
    name='Werkzeug',
    version='0.2',
    url='http://werkzeug.pocoo.org/',
    download_url='http://trac.pocoo.org/repos/werkzeug/trunk',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='The Swiss Army knife of Python web development',
    long_description=getdoc(werkzeug),
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
