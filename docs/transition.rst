Transition to Werkzeug 1.0
==========================

Werkzeug originally had a magical import system hook that enabled
everything to be imported from one module and still loading the actual
implementations lazily as necessary.  Unfortunately this turned out to be
slow and also unreliable on alternative Python implementations and
Google's App Engine.

Starting with 0.7 we recommend against the short imports and strongly
encourage starting importing from the actual implementation module.
Werkzeug 1.0 will disable the magical import hook completely.

Because finding out where the actual functions are imported and rewriting
them by hand is a painful and boring process we wrote a tool that aids in
making this transition.

Automatically Rewriting Imports
-------------------------------

For instance, with Werkzeug < 0.7 the recommended way to use the escape function
was this::

    from werkzeug import escape

With Werkzeug 0.7, the recommended way to import this function is
directly from the utils module (and with 1.0 this will become mandatory).
To automatically rewrite all imports one can use the
`werkzeug-import-rewrite <https://bit.ly/import-rewrite>`_ script.

You can use it by executing it with Python and with a list of folders with
Werkzeug based code.  It will then spit out a hg/git compatible patch
file.  Example patch file creation::

    $ python werkzeug-import-rewrite.py . > new-imports.udiff

To apply the patch one of the following methods work:

hg:

    ::

        hg import new-imports.udiff

git:

    ::

        git apply new-imports.udiff

patch:

    ::

        patch -p1 < new-imports.udiff


Deprecated and Removed Code
---------------------------

Some things that were relevant to Werkzeug's core (working with WSGI and
HTTP) have been removed. These were not commonly used, or are better
served by dedicated libraries.

-   ``werkzeug.script``, replace with `Click`_ or another dedicated
    command line library.
-   ``werkzeug.template``, replace with `Jinja`_ or another dedicated
    template library.
-   ``werkzeug.contrib.jsrouting``, this type of URL generation in
    JavaScript did not scale well. Instead, generate URLs when
    rendering templates, or add a URL field to a JSON response.
-   ``werkzeug.contrib.kickstart``, replace with custom code if needed,
    the Werkzeug API has improved in general. `Flask`_ is a higher-level
    version of this.
-   ``werkzeug.contrib.testtools``, was not significantly useful over
    the default behavior.
-   ``werkzeug.contrib.cache``, has been extracted to `cachelib`_.
-   ``werkzeug.contrib.atom``, was outside the core focus of Werkzeug,
    replace with a dedicated feed generation library.
-   ``werkzeug.contrib.limiter``, stream limiting is better handled by
    the WSGI server library instead of middleware.

.. _Click: https://click.palletsprojects.com/
.. _Jinja: http://jinja.pocoo.org/docs/
.. _Flask: http://flask.pocoo.org/docs/
.. _cachelib: https://github.com/pallets/cachelib
