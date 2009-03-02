# -*- coding: utf-8 -*-
"""
    werkzeug
    ~~~~~~~~

    Werkzeug is the Swiss Army knife of Python web development.

    It provides useful classes and functions for any WSGI application to make
    the life of a python web developer much easier.  All of the provided
    classes are independent from each other so you can mix it with any other
    library.


    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from types import ModuleType
import sys


all_by_module = {
    'werkzeug.debug':       ['DebuggedApplication'],
    'werkzeug.local':       ['Local', 'LocalManager', 'LocalProxy'],
    'werkzeug.templates':   ['Template'],
    'werkzeug.serving':     ['run_simple'],
    'werkzeug.test':        ['Client', 'EnvironBuilder', 'create_environ',
                             'run_wsgi_app'],
    'werkzeug.testapp':     ['test_app'],
    'werkzeug.exceptions':  ['abort', 'Aborter'],
    'werkzeug.utils':       ['escape', 'url_quote',
                             'environ_property', 'cookie_date', 'http_date',
                             'url_encode', 'url_quote_plus', 'url_fix',
                             'get_host', 'responder',
                             'SharedDataMiddleware', 'ClosingIterator',
                             'FileStorage', 'url_unquote_plus', 'url_decode',
                             'url_unquote', 'get_current_url', 'redirect',
                             'append_slash_redirect',
                             'cached_property', 'import_string',
                             'dump_cookie', 'parse_cookie', 'unescape',
                             'format_string', 'Href', 'DispatcherMiddleware',
                             'find_modules', 'header_property', 'html',
                             'xhtml', 'HTMLBuilder', 'parse_form_data',
                             'validate_arguments', 'ArgumentValidationError',
                             'bind_arguments', 'FileWrapper', 'wrap_file',
                             'pop_path_info', 'peek_path_info',
                             'LimitedStream', 'secure_filename'],
    'werkzeug.datastructures': ['MultiDict', 'CombinedMultiDict', 'Headers',
                             'EnvironHeaders', 'ImmutableList',
                             'ImmutableDict', 'ImmutableMultiDict',
                             'TypeConversionDict', 'ImmutableTypeConversionDict',
                             'Accept', 'MIMEAccept', 'CharsetAccept',
                             'LanguageAccept', 'RequestCacheControl',
                             'ResponseCacheControl', 'ETags', 'HeaderSet',
                             'WWWAuthenticate', 'Authorization',
                             'CacheControl', 'FileMultiDict', 'CallbackDict'],
    'werkzeug.useragents':  ['UserAgent'],
    'werkzeug.http':        ['parse_etags', 'parse_date', 'parse_cache_control_header',
                             'is_resource_modified', 'parse_accept_header',
                             'parse_set_header', 'quote_etag', 'unquote_etag',
                             'generate_etag', 'dump_header',
                             'parse_list_header', 'parse_dict_header',
                             'parse_authorization_header',
                             'parse_www_authenticate_header',
                             'remove_entity_headers', 'is_entity_header',
                             'remove_hop_by_hop_headers', 'parse_options_header',
                             'dump_options_header', 'is_hop_by_hop_header',
                             'unquote_header_value',
                             'quote_header_value', 'HTTP_STATUS_CODES'],
    'werkzeug.wrappers':    ['BaseResponse', 'BaseRequest', 'Request',
                             'Response', 'AcceptMixin', 'ETagRequestMixin',
                             'ETagResponseMixin', 'ResponseStreamMixin',
                             'CommonResponseDescriptorsMixin',
                             'UserAgentMixin', 'AuthorizationMixin',
                             'WWWAuthenticateMixin',
                             'CommonRequestDescriptorsMixin'],
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

# figure out the version
try:
    version = __import__('pkg_resources').get_distribution('Werkzeug').version
except:
    version = 'unknown'

# setup the new module and patch it into the dict of loaded modules
new_module = sys.modules['werkzeug'] = module('werkzeug')
new_module.__dict__.update({
    '__file__':         __file__,
    '__path__':         __path__,
    '__doc__':          __doc__,
    '__all__':          tuple(object_origins) + tuple(attribute_modules),
    '__docformat__':    'restructuredtext en',
    '__version__':      version
})
