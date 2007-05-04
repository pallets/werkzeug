# -*- coding: utf-8 -*-
"""
    werkzeug.routing
    ~~~~~~~~~~~~~~~~

    An extensible URL mapper.

    Defining routes::

        >>> from werkzeug.routing import Map, Rule
        >>> m = Map([
        ...  Rule('/', endpoint='static/index'),
        ...  Rule('/downloads/', endpoint='downloads/index'),
        ...  Rule('/downloads/<int:download_id>', endpoint='downloads/show'),
        ...  Rule('/', subdomain='cache', endpoint='cache/information'),
        ...  Rule('/<hexstring(30):hash>', subdomain='cache',
        ...        endpoint='cache/get_file')
        ... ], default_subdomain='www', subdomain_aliases={'': 'www'})

    Building URLs::

        >>> builder = m.get_builder('http', 'www.myserver.com', '/', 'utf-8')
        >>> builder.url_for('cache/information')
        'http://cache.myserver.com/'
        >>> builder.url_for('downloads/show', download_id=42)
        '/downloads/42'
        >>> builder.external_url_for('downloads/show', download_id=23)
        'http://www.myserver.com/downloads/23'

    Matching URLs::

        >>> m.get_matcher('www.myserver.com', '/')
        >>> m.match('/downloads/42')
        ('downloads/index', {})
        >>> m.match('/missing')
        Traceback (most recent call last):
        ...
        NotFound('/missing')
        >>> m.match('/downloads/42')
        ('downloads/show', {'download_id': 42})

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
        (?P<converter>[a-zA-Z_][a-zA-Z0-9_]*)     # converter name
        (?:\((?P<args>[^\)]*)\))?               # converter arguments
        \:                                      # variable delimiter
    )?
    (?P<variable>[a-zA-Z_][a-zA-Z0-9_]*)        # variable name
    >
''')

_arg_split_re = re.compile(r',\s*')


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
        else:
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


def parse_arguments(string, *defaults):
    """
    Helper function for the converters.
    """
    missing = object()
    args = dict(enumerate(_arg_split_re.split(string)))
    for idx, (type, default_value) in enumerate(defaults):
        value = args.pop(idx, missing)
        if value is missing:
            value = default_value
        else:
            value = type(value)
        yield value


class RoutingException(Exception):
    """
    Special exceptions that require the application to redirect, notifies
    him about missing urls etc.
    """


class RequestRedirect(RoutingException):
    """
    Raise if the map requests a redirect. This is for example the case
    if `strict_slashes` are activated and an url that requires a leading
    slash.
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
    You'll receive this warning if there the mapper is in `strict_slashes`
    mode and there is an url that requires a trailing slash and the same
    url without that slash would lead to a different page.
    """


class Rule(object):
    """
    Represents one url.
    """

    def __init__(self, string, endpoint=None, strict_slash=None):
        self.rule = string
        self.map = None
        self.strict_slash = strict_slash
        self.endpoint = endpoint

        self._trace = []
        self._arguments = set()
        self._converters = {}
        self._regex = None

    def bind(self, map):
        if self.map is not None:
            raise RuntimeError('rule %r already bound to %r' % (self, map))
        self.map = map
        if self.strict_slash is None:
            self.strict_slash = map.strict_slash

    def compile(self):
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

        self._regex = re.compile(r'^%s%s$(?u)' % (
            u''.join(tmp),
            not self.strict_slash and '/?' or ''
        ))

    def match(self, path):
        if self._regex is None:
            self.compile()
        m =  self._regex.search(path)
        if m is not None:
            result = {}
            for name, value in m.groupdict().iteritems():
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
        return cmp(self._complexity, other._complexity)


class BaseConverter(object):

    def __init__(self, map, args):
        self.map = map
        self.args = args

    def get_regex(self):
        return '[^/]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return quote_plus(unicode(value).encode(map.charset))


class UnicodeConverter(BaseConverter):

    def __init__(self, map, args):
        super(BaseConverter, self).__init__(map, args)
        min_length, max_length = parse_arguments(args, (int, -1),
                                                 (int, -1))


class Map(object):
    """
    The base class for all the url maps.
    """

    def __init__(self, rules, charset='utf-8', strict_slash=False):
        self._rules = []

        self.charset = charset
        self.strict_slash = strict_slash

        self.converters = {
            'int':          IntegerConverter,
            'float':        FloatConverter,
            'string':       UnicodeConverter,
            'default':      UnicodeConverter,
            'hexstring':    HexstringConverter
        }

        for rule in rules:
            self.connect(rule)
        self.finish()

    def connect(self, rule):
        if not isinstance(rule, Rule):
            raise TypeError('rule objects required')
        rule.bind(self)
        self._rules.append(rule)

    def finish(self):
        self._rules.sort()

    def match(self, path_info=''):
        path = '<%s>/%s' (subdomain, path_info.lstrip('/'))
        for rule in self._rules:
            rv = rule.match(path)
            if rv is not None:
                return rule.endpoint, rv
        raise NotFound(path_info)
