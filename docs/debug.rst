Debugging Applications
======================

.. module:: werkzeug.debug

Depending on the WSGI gateway/server, exceptions are handled
differently. Most of the time, exceptions go to stderr or the error log,
and a generic "500 Internal Server Error" message is displayed.

Since this is not the best debugging environment, Werkzeug provides a
WSGI middleware that renders nice tracebacks, optionally with an
interactive debug console to execute code in any frame.

.. danger::

    The debugger allows the execution of arbitrary code which makes it a
    major security risk. **The debugger must never be used on production
    machines. We cannot stress this enough. Do not enable the debugger
    in production.**

.. note::

    The interactive debugger does not work in forking environments, such
    as a server that starts multiple processes. Most such environments
    are production servers, where the debugger should not be enabled
    anyway.


Enabling the Debugger
---------------------

Enable the debugger by wrapping the application with the
:class:`DebuggedApplication` middleware. Alternatively, you can pass
``use_debugger=True`` to :func:`run_simple` and it will do that for you.

.. autoclass:: DebuggedApplication


Using the Debugger
------------------

Once enabled and an error happens during a request you will see a
detailed traceback instead of a generic "internal server error". The
traceback is still output to the terminal as well.

The error message is displayed at the top. Clicking it jumps to the
bottom of the traceback. Frames that represent user code, as opposed to
built-ins or installed packages, are highlighted blue. Clicking a
frame will show more lines for context, clicking again will hide them.

If you have the ``evalex`` feature enabled you can get a console for
every frame in the traceback by hovering over a frame and clicking the
console icon that appears at the right. Once clicked a console opens
where you can execute Python code in:

.. image:: _static/debug-screenshot.png
   :alt: a screenshot of the interactive debugger
   :align: center

Inside the interactive consoles you can execute any kind of Python code.
Unlike regular Python consoles the output of the object reprs is colored
and stripped to a reasonable size by default. If the output is longer
than what the console decides to display a small plus sign is added to
the repr and a click will expand the repr.

To display all variables that are defined in the current frame you can
use the ``dump()`` function. You can call it without arguments to get a
detailed list of all variables and their values, or with an object as
argument to get a detailed list of all the attributes it has.


Debugger PIN
------------

Starting with Werkzeug 0.11 the debug console is protected by a PIN.
This is a security helper to make it less likely for the debugger to be
exploited if you forget to disable it when deploying to production. The
PIN based authentication is enabled by default.

The first time a console is opened, a dialog will prompt for a PIN that
is printed to the command line. The PIN is generated in a stable way
that is specific to the project. An explicit PIN can be provided through
the environment variable ``WERKZEUG_DEBUG_PIN``. This can be set to a
number and will become the PIN. This variable can also be set to the
value ``off`` to disable the PIN check entirely.

If an incorrect PIN is entered too many times the server needs to be
restarted.

**This feature is not meant to entirely secure the debugger. It is
intended to make it harder for an attacker to exploit the debugger.
Never enable the debugger in production.**


Pasting Errors
--------------

If you click on the "Traceback (most recent call last)" header, the
view switches to a tradition text-based traceback. The text can be
copied, or automatically pasted to `gist.github.com
<https://gist.github.com>`_ with one click.
