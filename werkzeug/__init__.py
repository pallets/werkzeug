# -*- coding: utf-8 -*-
"""
    werkzeug
    ~~~~~~~~

    Werkzeug is the Swiss Army® knife of Python web development.

    It provides useful classes and functions for any WSGI application take
    make life much easier.  All of the provided classes are independed from
    each other so you can mix it with any other library.


    Builtin blades^Wfeatures
    ~~~~~~~~~~~~~~~~~~~~~~~~

    **Request / Response objects**

        These objects wrap the WSGI `environ` and `start_response` objects.
        They handle unicode conversion, form data parsing, cookie management
        and much more in a django like manner.

        Just subclass them and hook your own features in.

    **Reporter stream**

        A class that can wrap a `wsgi.input` stream so that it reports it's
        progress into the active session, a file on the filesystem etc.  This
        is very useful if you want to give your users a visual feedback for
        file uploads using AJAX.

    **Application debugger middleware**

        If you want to debug your WSGI application you can hook in the
        `DebuggedApplication` middleware that allows you to inspect the frames
        of tracebacks either by looking at the current locals and sourcecode
        or starting an interactive shell in one of the frames.

    **Shared data middleware**

        In production environments static data is usually served by a
        lightweight webserver like lighttpd or nginx.  But during development
        it makes no sense to install another service on the computer so the
        `SharedDataMiddleware` can serve static files in your WSGI application.

    **Unicode aware data processing**

        The utils package contains functions that work like their counterparts
        in the builtin `urllib` or `cgi` module but are unicode aware.  Per
        default they expect utf-8 strings like the request/response objects
        but you can pass an encoding to the too.

    **Mini template engine**

        For small projects you often face the problem that a real template
        engine means another requirement but the builtin string formattings
        (or string template) operations are not enough for the application.
        Werkzeug provides a minimal template engine that looks and behaves
        like the e-ruby template engine.

    **Context Locals**

        The `Local` object works pretty much like a normal thread local but
        it has support for py.magic greenlets too.  Additionally there is a
        `LocalManager` that allows you to clean up all the context locals you
        have instanciated.

    **Test utilities**

        Werkzeug provides a `Client` class that can be used to test
        applications.  Just instanciate it with the app and fire virtual
        requests.


    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from types import ModuleType
import sys


object_origins = {
    'BaseRequest':          'werkzeug.wrappers',
    'BaseResponse':         'werkzeug.wrappers',
    'BaseReporterStream':   'werkzeug.wrappers',
    'DebuggedApplication':  'werkzeug.debug',
    'Template':             'werkzeug.minitmpl',
    'Client':               'werkzeug.test',
    'Local':                'werkzeug.locals',
    'LocalManager':         'werkzeug.locals',
    'run_simple':           'werkzeug.serving',
    'SharedDataMiddleware': 'werkzeug.utils',
    'ClosingIterator':      'werkzeug.utils',
    'environ_property':     'werkzeug.utils',
    'parse_accept_header':  'werkzeug.utils',
    'url_decode':           'werkzeug.utils',
    'url_encode':           'werkzeug.utils',
    'url_quote':            'werkzeug.utils',
    'url_unquote':          'werkzeug.utils',
    'url_quote_plus':       'werkzeug.utils',
    'url_unquote_plus':     'werkzeug.utils',
    'escape':               'werkzeug.utils'
}

all_by_module = {}
for name, module in object_origins.iteritems():
    all_by_module.setdefault(module, []).append(name)


class _AutoModule(ModuleType):
    """Automatically import objects from the modules."""

    def __getattr__(self, name):
        if name in object_origins:
            module = __import__(object_origins[name], None, None, [name])
            for extra_name in all_by_module[module.__name__]:
                setattr(self, extra_name, getattr(module, extra_name))
            return getattr(module, name)
        return ModuleType.__getattribute__(self, name)


old_module = sys.modules['werkzeug']
new_module = sys.modules['werkzeug'] = _AutoModule('werkzeug')
new_module.__dict__.update(
    __file__=__file__,
    __path__=__path__,
    __doc__=__doc__,
    __all__=tuple(object_origins)
)
