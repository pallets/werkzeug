#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Werkzeug Import Rewriter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Changes the deprecated werkzeug imports to the full canonical imports.
    This is a terrible hack, don't trust the diff untested.

    :copyright: (c) 2011 by the Werkzeug Team.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
import sys
import os
import re
import posixpath
import difflib


_from_import_re = re.compile(r'(\s*(>>>|\.\.\.)?\s*)from werkzeug import\s+')
_direct_usage = re.compile('(?<!`)(werkzeug\.)([a-zA-Z_][a-zA-Z0-9_]+)')


# not necessarily in sync with current werkzeug/__init__.py
all_by_module = {
    'werkzeug.debug':       ['DebuggedApplication'],
    'werkzeug.local':       ['Local', 'LocalManager', 'LocalProxy',
                             'LocalStack', 'release_local'],
    'werkzeug.templates':   ['Template'],
    'werkzeug.serving':     ['run_simple'],
    'werkzeug.test':        ['Client', 'EnvironBuilder', 'create_environ',
                             'run_wsgi_app'],
    'werkzeug.testapp':     ['test_app'],
    'werkzeug.exceptions':  ['abort', 'Aborter'],
    'werkzeug.urls':        ['url_decode', 'url_encode', 'url_quote',
                             'url_quote_plus', 'url_unquote',
                             'url_unquote_plus', 'url_fix', 'Href',
                             'iri_to_uri', 'uri_to_iri'],
    'werkzeug.formparser':  ['parse_form_data'],
    'werkzeug.utils':       ['escape', 'environ_property', 'cookie_date',
                             'http_date', 'append_slash_redirect', 'redirect',
                             'cached_property', 'import_string',
                             'dump_cookie', 'parse_cookie', 'unescape',
                             'format_string', 'find_modules', 'header_property',
                             'html', 'xhtml', 'HTMLBuilder',
                             'validate_arguments', 'ArgumentValidationError',
                             'bind_arguments', 'secure_filename'],
    'werkzeug.wsgi':        ['get_current_url', 'get_host', 'pop_path_info',
                             'peek_path_info', 'SharedDataMiddleware',
                             'DispatcherMiddleware', 'ClosingIterator',
                             'FileWrapper', 'make_line_iter', 'LimitedStream',
                             'responder', 'wrap_file', 'extract_path_info'],
    'werkzeug.datastructures': ['MultiDict', 'CombinedMultiDict', 'Headers',
                             'EnvironHeaders', 'ImmutableList',
                             'ImmutableDict', 'ImmutableMultiDict',
                             'TypeConversionDict', 'ImmutableTypeConversionDict',
                             'Accept', 'MIMEAccept', 'CharsetAccept',
                             'LanguageAccept', 'RequestCacheControl',
                             'ResponseCacheControl', 'ETags', 'HeaderSet',
                             'WWWAuthenticate', 'Authorization',
                             'FileMultiDict', 'CallbackDict', 'FileStorage',
                             'OrderedMultiDict', 'ImmutableOrderedMultiDict'],
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
    'werkzeug.security':    ['generate_password_hash', 'check_password_hash'],
    # the undocumented easteregg ;-)
    'werkzeug._internal':   ['_easteregg']
}

by_item = {}
for module, names in all_by_module.iteritems():
    for name in names:
        by_item[name] = module


def find_module(item):
    return by_item.get(item, 'werkzeug')


def complete_fromlist(fromlist, lineiter):
    fromlist = fromlist.strip()
    if not fromlist:
        return []
    if fromlist[0] == '(':
        if fromlist[-1] == ')':
            return fromlist[1:-1].strip().split(',')
        fromlist = fromlist[1:].strip().split(',')
        for line in lineiter:
            line = line.strip()
            abort = False
            if line.endswith(')'):
                line = line[:-1]
                abort = True
            fromlist.extend(line.split(','))
            if abort:
                break
        return fromlist
    elif fromlist[-1] == '\\':
        fromlist = fromlist[:-1].strip().split(',')
        for line in lineiter:
            line = line.strip()
            abort = True
            if line.endswith('\\'):
                abort = False
                line = line[:-1]
            fromlist.extend(line.split(','))
            if abort:
                break
        return fromlist
    return fromlist.split(',')


def rewrite_from_imports(fromlist, indentation, lineiter):
    parsed_items = []
    for item in complete_fromlist(fromlist, lineiter):
        item = item.strip().split()
        if not item:
            continue
        if len(item) == 1:
            parsed_items.append((item[0], None))
        elif len(item) == 3 and item[1] == 'as':
            parsed_items.append((item[0], item[2]))
        else:
            raise ValueError('invalid syntax for import')

    new_imports = {}
    for item, alias in parsed_items:
        new_imports.setdefault(find_module(item), []).append((item, alias))

    for module_name, items in sorted(new_imports.items()):
        fromlist_items = sorted(['%s%s' % (
            item,
            alias is not None and (' as ' + alias) or ''
        ) for (item, alias) in items], reverse=True)

        prefix = '%sfrom %s import ' % (indentation, module_name)
        item_buffer = []
        while fromlist_items:
            item_buffer.append(fromlist_items.pop())
            fromlist = ', '.join(item_buffer)
            if len(fromlist) + len(prefix) > 79:
                yield prefix + ', '.join(item_buffer[:-1]) + ', \\'
                item_buffer = [item_buffer[-1]]
                # doctest continuations
                indentation = indentation.replace('>', '.')
                prefix = indentation + '     '
        yield prefix + ', '.join(item_buffer)


def inject_imports(lines, imports):
    pos = 0
    for idx, line in enumerate(lines):
        if re.match(r'(from|import)\s+werkzeug', line):
            pos = idx
            break
    lines[pos:pos] = ['from %s import %s' % (mod, ', '.join(sorted(attrs)))
                      for mod, attrs in sorted(imports.items())]


def rewrite_file(filename):
    with open(filename) as f:
        old_file = f.read().splitlines()

    new_file = []
    deferred_imports = {}
    lineiter = iter(old_file)
    for line in lineiter:
        # rewrite from imports
        match = _from_import_re.search(line)
        if match is not None:
            fromlist = line[match.end():]
            new_file.extend(rewrite_from_imports(fromlist,
                                                 match.group(1),
                                                 lineiter))
            continue
        # rewrite attribute access to 'werkzeug'
        def _handle_match(match):
            attr = match.group(2)
            mod = find_module(attr)
            if mod == 'werkzeug':
                return match.group(0)
            deferred_imports.setdefault(mod, []).append(attr)
            return attr
        new_file.append(_direct_usage.sub(_handle_match, line))
    if deferred_imports:
        inject_imports(new_file, deferred_imports)

    for line in difflib.unified_diff(old_file, new_file,
                     posixpath.normpath(posixpath.join('a', filename)),
                     posixpath.normpath(posixpath.join('b', filename)),
                     lineterm=''):
        print line


def rewrite_in_folders(folders):
    for folder in folders:
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                filename = os.path.join(dirpath, filename)
                if filename.endswith(('.rst', '.py')):
                    rewrite_file(filename)


def main():
    if len(sys.argv) == 1:
        print 'usage: werkzeug-import-rewrite.py [folders]'
        sys.exit(1)
    rewrite_in_folders(sys.argv[1:])


if __name__ == '__main__':
    main()
