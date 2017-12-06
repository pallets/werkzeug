#!/usr/bin/env python
import io
import re

from setuptools import find_packages, setup

with io.open('README.rst', 'rt', encoding='utf8') as f:
    readme = f.read()

with io.open('werkzeug/__init__.py', 'rt', encoding='utf8') as f:
    version = re.search(
        r'__version__ = \'(.*?)\'', f.read(), re.M).group(1)

setup(
    name='Werkzeug',
    version=version,
    url='https://www.palletsprojects.org/p/werkzeug/',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='The comprehensive WSGI web application library.',
    long_description=readme,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(exclude=('tests*',)),
    extras_require={
        'watchdog': ['watchdog'],
        'termcolor': ['termcolor'],
        'dev': [
            'pytest',
            'coverage',
            'tox',
            'sphinx',
        ],
    },
    include_package_data=True,
    zip_safe=False,
    platforms='any'
)
