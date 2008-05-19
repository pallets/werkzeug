# -*- coding: utf-8 -*-
"""
    werkzeug
    ~~~~~~~~

    Werkzeug is the Swiss Army knife of Python web development.

    It provides useful classes and functions for any WSGI application to make
    the life of a python web developer much easier.  All of the provided
    classes are independed from each other so you can mix it with any other
    library.


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from types import ModuleType
import sys


all_by_module = {
    'werkzeug.debug':       ['DebuggedApplication'],
    'werkzeug.local':       ['Local', 'LocalManager', 'LocalProxy'],
    'werkzeug.templates':   ['Template'],
    'werkzeug.serving':     ['run_simple'],
    'werkzeug.test':        ['Client'],
    'werkzeug.testapp':     ['test_app'],
    'werkzeug.exceptions':  ['abort', 'Aborter'],
    'werkzeug.utils':       ['escape', 'create_environ', 'url_quote',
                             'environ_property', 'cookie_date', 'http_date',
                             'url_encode', 'url_quote_plus', 'Headers',
                             'EnvironHeaders', 'CombinedMultiDict', 'url_fix',
                             'run_wsgi_app', 'get_host', 'responder',
                             'SharedDataMiddleware', 'ClosingIterator',
                             'FileStorage', 'url_unquote_plus', 'url_decode',
                             'url_unquote', 'get_current_url', 'redirect',
                             'append_slash_redirect',
                             'cached_property', 'MultiDict', 'import_string',
                             'dump_cookie', 'parse_cookie', 'unescape',
                             'format_string', 'Href', 'DispatcherMiddleware',
                             'find_modules', 'header_property', 'html',
                             'xhtml', 'HTMLBuilder', 'parse_form_data',
                             'validate_arguments', 'ArgumentValidationError'],
    'werkzeug.useragents':  ['UserAgent'],
    'werkzeug.http':        ['Accept', 'CacheControl', 'ETags', 'parse_etags',
                             'parse_date', 'parse_cache_control_header',
                             'is_resource_modified', 'parse_accept_header',
                             'parse_set_header', 'quote_etag', 'unquote_etag',
                             'generate_etag', 'dump_header',
                             'parse_list_header', 'parse_dict_header',
                             'HeaderSet', 'parse_authorization_header',
                             'parse_www_authenticate_header',
                             'WWWAuthenticate', 'Authorization',
                             'HTTP_STATUS_CODES'],
    'werkzeug.wrappers':    ['BaseResponse', 'BaseRequest', 'Request',
                             'Response', 'AcceptMixin', 'ETagRequestMixin',
                             'ETagResponseMixin', 'ResponseStreamMixin',
                             'CommonResponseDescriptorsMixin',
                             'UserAgentMixin', 'AuthorizationMixin',
                             'WWWAuthenticateMixin'],
    # the undocumented easteregg ;-)
    'werkzeug._internal':   ['_easteregg']
}

attribute_modules = dict.fromkeys(['exceptions', 'routing', 'script'])


object_origins = {}
for module, items in all_by_module.iteritems():
    for item in items:
        object_origins[item] = module


class module(ModuleType):
    """Automatically import objects from the modules."""

    def __getattr__(self, name):
        if name in object_origins:
            module = __import__(object_origins[name], None, None, [name])
            for extra_name in all_by_module[module.__name__]:
                setattr(self, extra_name, getattr(module, extra_name))
            return getattr(module, name)
        elif name in attribute_modules:
            __import__('werkzeug.' + name)
        return ModuleType.__getattribute__(self, name)


# keep a reference to this module so that it's not garbage collected
old_module = sys.modules['werkzeug']

# setup the new module and patch it into the dict of loaded modules
new_module = sys.modules['werkzeug'] = module('werkzeug')
new_module.__dict__.update({
    '__file__': __file__,
    '__path__': __path__,
    '__doc__':  __doc__,
    '__all__':  tuple(object_origins) + tuple(attribute_modules)
})
