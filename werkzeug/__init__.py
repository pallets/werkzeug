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

# This import magic raises concerns quite often which is why the implementation
# and motiviation is explained here in detail now.
#
# The majority of the functions and classes provided by Werkzeug work on the
# HTTP and WSGI layer.  There is no useful grouping for those which is why
# they are all importable from "werkzeug" instead of the modules where they are
# implemented.  The downside of that is, that now everything would be loaded at
# once, even if unused.
#
# The implementation of a lazy-loading module in this file replaces the
# werkzeug package when imported from within.  Attribute access to the werkzeug
# module will then lazily import from the modules that implement the objects.


# import mapping to objects in other modules
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
                             'LimitedStream', 'make_line_iter',
                             'secure_filename'],
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

# modules that should be imported when accessed as attributes of werkzeug
attribute_modules = dict.fromkeys(['exceptions', 'routing', 'script'])


object_origins = {}
for module, items in all_by_module.iteritems():
    for item in items:
        object_origins[item] = module


#: the cached version of the library.  We get the distribution from
#: pkg_resources the first time this attribute is accessed.  Because
#: this operation is quite slow it speeds up importing a lot.
version = None

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

    def __dir__(self):
        """Just show what we want to show."""
        result = list(new_module.__all__)
        result.extend(('__file__', '__path__', '__doc__', '__all__',
                       '__docformat__', '__name__', '__path__',
                       '__package__', '__version__'))
        return result

    @property
    def __version__(self):
        global version
        if version is None:
            try:
                version = __import__('pkg_resources') \
                          .get_distribution('Werkzeug').version
            except:
                version = 'unknown'
        return version

# keep a reference to this module so that it's not garbage collected
old_module = sys.modules['werkzeug']


# setup the new module and patch it into the dict of loaded modules
new_module = sys.modules['werkzeug'] = module('werkzeug')
new_module.__dict__.update({
    '__file__':         __file__,
    '__path__':         __path__,
    '__doc__':          __doc__,
    '__all__':          tuple(object_origins) + tuple(attribute_modules),
    '__docformat__':    'restructuredtext en'
})
