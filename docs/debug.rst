======================
Debugging Applications
======================

.. module:: werkzeug.debug

Depending on the WSGI gateway/server, exceptions are handled differently.
But most of the time, exceptions go to stderr or the error log.

Since this is not the best debugging environment, Werkzeug provides a
WSGI middleware that renders nice debugging tracebacks, optionally with an
AJAX based debugger (which allows to execute code in the context of the
traceback's frames).

The interactive debugger however does not work in forking environments
which makes it nearly impossible to use on production servers.  Also the
debugger allows the execution of arbitrary code which makes it a major
security risk and **must never be used on production machines** because of
that.  **We cannot stress this enough.  Do not enable this in
production.**

Enabling the Debugger
=====================

You can enable the debugger by wrapping the application in a
:class:`DebuggedApplication` middleware.  Additionally there are
parameters to the :func:`run_simple` function to enable it because this
is a common task during development.

.. autoclass:: DebuggedApplication

Using the Debugger
==================

Once enabled and an error happens during a request you will see a detailed
traceback instead of a general "internal server error".  If you have the
`evalex` feature enabled you can also get a traceback for every frame in
the traceback by clicking on the console icon.

Once clicked a console opens where you can execute Python code in:

.. image:: _static/debug-screenshot.png
   :alt: a screenshot of the interactive debugger
   :align: center

Inside the interactive consoles you can execute any kind of Python code.
Unlike regular Python consoles the output of the object reprs is colored
and stripped to a reasonable size by default.  If the output is longer
than what the console decides to display a small plus sign is added to
the repr and a click will expand the repr.

To display all variables that are defined in the current frame you can
use the `dump()` function.  You can call it without arguments to get a
detailed list of all variables and their values, or with an object as
argument to get a detailed list of all the attributes it has.

Debugger PIN
============

Starting with Werkzeug 0.11 the debugger is additionally protected by a
PIN.  This is a security helper to make it less likely for the debugger to
be exploited in production as it has happened to people to keep the
debugger active.  The PIN based authentication is enabled by default.

When the debugger comes up, on first usage it will prompt for a PIN that
is printed to the command line.  The PIN is generated in a stable way that
is specific to the project.  In some situations it might be not possible
to generate a stable PIN between restarts in which case an explicit PIN
can be provided through the environment variable ``WERKZEUG_DEBUG_PIN``.
This can be set to a number and will become the PIN.  This variable can
also be set to the value ``off`` to disable the PIN check entirely.

If the PIN is entered too many times incorrectly the server needs to be
restarted.

**This feature is not supposed to entirely secure the debugger.  It's
intended to make it harder for an attacker to exploit the debugger.  Never
enable the debugger in production.**

Pasting Errors
==============

If you click on the `Traceback` title, the traceback switches over to a text
based one.  The text based one can be pasted to `gist.github.com <https://gist.github.com>`_ with one
click.


.. _paste.pocoo.org: https://gist.github.com

