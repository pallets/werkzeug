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
`werkzeug-import-rewrite <http://bit.ly/import-rewrite>`_ script.

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

Stop Using Deprecated Things
----------------------------

A few things in Werkzeug will stop being supported and for others, we're
suggesting alternatives even if they will stick around for a longer time.

Do not use:

-   `werkzeug.script`, replace it with custom scripts written with
    `argparse` or something similar.
-   `werkzeug.template`, replace with a proper template engine.
-   `werkzeug.contrib.jsrouting`, stop using URL generation for
    JavaScript, it does not scale well with many public routing.
-   `werkzeug.contrib.kickstart`, replace with hand written code, the
    Werkzeug API became better in general that this is no longer
    necessary.
-   `werkzeug.contrib.testtools`, not useful really.
