# -*- coding: utf-8 -*-
"""
    werkzeug.routing
    ~~~~~~~~~~~~~~~~

    An extensible URL mapper.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import re
from urllib import quote_plus
try:
    set
except NameError:
    from sets import Set as set


_rule_re = re.compile(r'''(?x)
    (?P<static>[^<]*)                           # static rule data
    <
    (?:
        (?P<converter>[a-zA-Z_][a-zA-Z0-9_]*)   # converter name
        (?:\((?P<args>[^\)]*)\))?               # converter arguments
        \:                                      # variable delimiter
    )?
    (?P<variable>[a-zA-Z][a-zA-Z0-9_]*)         # variable name
    >
''')


def parse_rule(rule):
    """
    Parse a rule and return it as generator. Each iteration yields
    tuples in the form ``(converter, arguments, variable)``. If the
    converter is `None` it's a static url part, otherwise it's a
    dynamic one.
    """
    pos = 0
    end = len(rule)
    do_match = _rule_re.match
    used_names = set()
    while pos < end:
        m = do_match(rule, pos)
        if m is None:
            break
        data = m.groupdict()
        if data['static']:
            yield None, None, data['static']
        variable = data['variable']
        converter = data['converter'] or 'default'
        if variable in used_names:
            raise ValueError('variable name %r used twice.' %
                             variable)
        used_names.add(variable)
        yield converter, data['args'] or None, variable
        pos = m.end()
    if pos < end:
        remaining = rule[pos:]
        if '>' in remaining or '<' in remaining:
            raise ValueError('malformed url rule')
        yield None, None, remaining


class RoutingException(Exception):
    """
    Special exceptions that require the application to redirect, notifies
    him about missing urls etc.
    """


class RequestRedirect(RoutingException):
    """
    Raise if the map requests a redirect. This is for example the case
    if `strict_slasheses` are activated and an url that requires a leading
    slash.
    """


class RequestSlash(RoutingException):
    """
    Internal exception never propagated.
    """


class NotFound(RoutingException, ValueError):
    """
    Raise if there is no match for the current url.
    """


class ValidationError(ValueError):
    """
    Validation error.
    """


class IneptUrl(Warning):
    """
    You'll receive this warning if there the mapper is in `strict_slasheses`
    mode and there is an url that requires a trailing slash and the same
    url without that slash would lead to a different page.
    """


class Rule(object):
    """
    Represents one url.
    """

    def __init__(self, string, subdomain=None, endpoint=None,
                 strict_slashes=None):
        if not string.startswith('/'):
            raise ValueError('urls must start with a leading slash')
        if string.endswith('/'):
            self.is_leaf = False
            string = string.rstrip('/')
        else:
            self.is_leaf = True
        self.rule = string

        self.map = None
        self.strict_slashes = strict_slashes
        self.subdomain = subdomain
        self.endpoint = endpoint

        self._trace = []
        self._arguments = set()
        self._converters = {}
        self._regex = None

    def bind(self, map):
        if self.map is not None:
            raise RuntimeError('rule %r already bound to %r' % (self, map))
        self.map = map
        if self.strict_slashes is None:
            self.strict_slashes = map.strict_slashes
        if self.subdomain is None:
            self.subdomain = map.default_subdomain

        if self.map is None:
            raise RuntimeError('cannot compile unbound rule')
        tmp = []
        for converter, arguments, variable in parse_rule(self.rule):
            if converter is None:
                tmp.append(re.escape(variable))
                self._trace.append((False, variable))
            else:
                f = self.map.converters[converter](self.map, arguments)
                tmp.append('(?P<%s>%s)' % (
                    variable,
                    f.regex
                ))
                self._converters[variable] = f
                self._trace.append((True, variable))
                self._arguments.add(variable)

        regex = r'^<%s>%s%s$(?u)' % (
            re.escape(self.subdomain),
            u''.join(tmp),
            not self.is_leaf and '(?P<__suffix__>/?)' or ''
        )
        self._regex = re.compile(regex)

    def match(self, path):
        m = self._regex.search(path)
        if m is not None:
            groups = m.groupdict()
            no_suffix = not groups.pop('__suffix__')
            # we have a folder like part of the url without a trailing
            # slash and strict slashes enabled. raise an error
            if self.strict_slashes and not self.is_leaf and no_suffix:
                raise RequestSlash()
            result = {}
            for name, value in groups.iteritems():
                try:
                    value = self._converters[name].to_python(value)
                except ValidationError:
                    return
                result[str(name)] = value
            return result

    def build(self, values):
        tmp = []
        for is_dynamic, data in self._trace:
            if is_dynamic:
                try:
                    value = self._converters[data].to_url(values[data])
                except ValidationError:
                    return
            else:
                tmp.append(data)
        return u''.join(tmp)

    def __cmp__(self, other):
        if not isinstance(other, Rule):
            return NotImplemented
        return cmp(len(self._trace), len(other._trace))


class BaseConverter(object):
    regex = '[^/]+'

    def __init__(self, map, args):
        self.map = map
        self.args = args

    def to_python(self, value):
        return value

    def to_url(self, value):
        return quote_plus(unicode(value).encode(map.charset))


class UnicodeConverter(BaseConverter):
    pass


class IntegerConverter(BaseConverter):
    regex = r'\d+'
    to_python = int


class FloatConverter(BaseConverter):
    regex = r'\d+\.\d+'
    to_python = float


class Builder(object):
    """
    Helper for url generation.
    """

    def __init__(self, map, url_scheme, server_name, subdomain, script_name):
        self.map = map
        self.url_scheme = url_scheme
        self.server_name = server_name
        self.subdomain = subdomain
        self.script_name = script_name


class Matcher(object):
    """
    Helper for url matching.
    """

    def __init__(self, map, server_name, subdomain, script_name):
        self.map = map
        self.server_name = server_name
        self.subdomain = subdomain
        self.script_name = script_name
        self._rules = self.map.rules

    def match(self, path_info):
        path = '<%s>/%s' % (self.subdomain, path_info.lstrip('/'))
        for rule in self._rules:
            try:
                rv = rule.match(path)
            except RequestSlash:
                raise RequestRedirect(path_info + '/')
            if rv is not None:
                return rule.endpoint, rv
        raise NotFound(path_info)


class Map(object):
    """
    The base class for all the url maps.
    """

    def __init__(self, rules, default_subdomain='www', charset='utf-8',
                 strict_slashes=False):
        self.rules = []

        self.charset = charset
        self.strict_slashes = strict_slashes
        self.default_subdomain = default_subdomain

        self.converters = {
            'int':          IntegerConverter,
            'float':        FloatConverter,
            'string':       UnicodeConverter,
            'default':      UnicodeConverter,
            #'hexstring':    HexstringConverter
        }

        for rule in rules:
            self.connect(rule)
        self.finish()

    def connect(self, rule):
        if not isinstance(rule, Rule):
            raise TypeError('rule objects required')
        rule.bind(self)
        self.rules.append(rule)

    def finish(self):
        self.rules.sort()

    def get_builder(self, server_name, script_name, url_scheme='http',
                    subdomain=None):
        if subdomain is None:
            subdomain = self.default_subdomain
        return Builder(self, url_scheme, server_name, subdomain, script_name)

    def get_matcher(self, server_name, script_name, subdomain=None):
        if subdomain is None:
            subdomain = self.default_subdomain
        return Matcher(self, server_name, subdomain, script_name)
