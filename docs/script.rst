===========================
Management Script Utilities
===========================

.. automodule:: werkzeug.script

.. admonition:: Deprecation

   `werkzeug.script` as a module is going away.  Please stop using it and
   replace it with custom scripts based on argparse.

Writing Actions
===============

Writing new action functions is pretty straightforward.  All you have to do is
to name the function `action_COMMAND` and it will be available as
`./manage.py COMMAND`.  The docstring of the function is used for the help
screen and all arguments must have defaults which the `run` function can
inspect.  As a matter of fact you cannot use ``*args`` or ``**kwargs``
constructs.

An additional feature is the definition of tuples as defaults.  The first item
in the tuple could be a short name for the command and the second the default
value::

    def action_add_user(username=('u', ''), password=('p', '')):
        """Docstring goes here."""
        ...


Action Discovery
================

Per default, the `run` function looks up variables in the current locals.
That means if no arguments are provided, it implicitly assumes this call::

    script.run(locals(), 'action_')

If you don't want to use an action discovery, you can set the prefix to an
empty string and pass a dict with functions::

    script.run(dict(
        runserver=script.make_runserver(make_app, use_reloader=True),
        shell=script.make_shell(lambda: {'app': make_app()}),
        initdb=on_initdb
    ), '')


Reference
=========

.. autofunction:: run

.. autofunction:: make_shell

.. autofunction:: make_runserver


Example Scripts
===============

In the Werkzeug `example folder`_ there are some ``./manage-APP.py`` scripts
using `werkzeug.script`.


.. _example folder: http://dev.pocoo.org/projects/werkzeug/browser/examples
