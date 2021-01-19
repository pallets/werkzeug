Installation
============


Python Version
--------------

We recommend using the latest version of Python. Werkzeug supports
Python 3.6 and newer.


Dependencies
------------

Werkzeug does not have any direct dependencies.


Optional dependencies
~~~~~~~~~~~~~~~~~~~~~

These distributions will not be installed automatically. Werkzeug will
detect and use them if you install them.

* `Colorama`_ provides request log highlighting when using the
  development server on Windows. This works automatically on other
  systems.
* `Watchdog`_ provides a faster, more efficient reloader for the
  development server.

.. _Colorama: https://pypi.org/project/colorama/
.. _Watchdog: https://pypi.org/project/watchdog/


Virtual environments
--------------------

Use a virtual environment to manage the dependencies for your project,
both in development and in production.

What problem does a virtual environment solve? The more Python
projects you have, the more likely it is that you need to work with
different versions of Python libraries, or even Python itself. Newer
versions of libraries for one project can break compatibility in
another project.

Virtual environments are independent groups of Python libraries, one for
each project. Packages installed for one project will not affect other
projects or the operating system's packages.

Python comes bundled with the :mod:`venv` module to create virtual
environments.


Create an environment
~~~~~~~~~~~~~~~~~~~~~

Create a project folder and a :file:`venv` folder within:

.. code-block:: sh

    mkdir myproject
    cd myproject
    python3 -m venv venv

On Windows:

.. code-block:: bat

    py -3 -m venv venv


Activate the environment
~~~~~~~~~~~~~~~~~~~~~~~~

Before you work on your project, activate the corresponding environment:

.. code-block:: sh

    . venv/bin/activate

On Windows:

.. code-block:: bat

    venv\Scripts\activate

Your shell prompt will change to show the name of the activated
environment.


Install Werkzeug
----------------

Within the activated environment, use the following command to install
Werkzeug:

.. code-block:: sh

    pip install Werkzeug
