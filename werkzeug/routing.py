# -*- coding: utf-8 -*-
"""
    werkzeug.routing
    ~~~~~~~~~~~~~~~~

    An extensible URL mapper.

    Map creation::

        >>> m = Map([
        ...     # Static URLs
        ...     Rule('/', endpoint='static/index'),
        ...     Rule('/about', endpoint='static/about'),
        ...     Rule('/help', endpoint='static/help'),
        ...     # Knowledge Base
        ...     Subdomain('kb', [
        ...         Rule('/', endpoint='kb/index'),
        ...         Rule('/browse/', endpoint='kb/browse'),
        ...         Rule('/browse/<int:id>/', endpoint='kb/browse'),
        ...         Rule('/browse/<int:id>/<int:page>', endpoint='kb/browse')
        ...     ])
        ... ], default_subdomain='www')

    URL building::

        >>> c = m.bind('example.com', '/')
        >>> c.build("kb/browse", dict(id=42))
        'http://kb.example.com/browse/42/'
        >>> c.build("kb/browse", dict())
        'http://kb.example.com/browse/'
        >>> c.build("kb/browse", dict(id=42, page=3))
        'http://kb.example.com/browse/42/3'
        >>> c.build("static/about")
        u'/about'
        >>> c.build("static/about", subdomain="kb")
        'http://www.example.com/about'
        >>> c.build("static/index", force_external=True)
        'http://www.example.com/'

    URL matching::

        >>> c = m.bind('example.com', '/')
        >>> c.match("/")
        ('static/index', {})
        >>> c.match("/about")
        ('static/about', {})
        >>> c = m.bind('example.com', '/', 'kb')
        >>> c.match("/", subdomain="kb")
        ('kb/index', {})
        >>> c.match("/browse/42/23", subdomain="kb")
        ('kb/browse', {'id': 42, 'page': 23})

    Exceptions::

        >>> m.match("/browse/42", subdomain="kb")
        Traceback (most recent call last):
        ...
        werkzeug.routing.RequestRedirect: http://kb.example.com/browse/42/
        >>> m.match("/missing", subdomain="kb")
        Traceback (most recent call last):
        ...
        werkzeug.routing.NotFound: /missing
        >>> m.match("/missing", subdomain="kb")


    :copyright: 2007 by Armin Ronacher, Leif K-Brooks.
    :license: BSD, see LICENSE for more details.
"""
import sys
import re
from urlparse import urljoin
from urllib import quote
from itertools import izip

from werkzeug.utils import url_encode, redirect, format_string
from werkzeug.exceptions import NotFound
try:
    set
except NameError:
    from sets import Set as set


_rule_re = re.compile(r'''
    (?P<static>[^<]*)                           # static rule data
    <
    (?:
        (?P<converter>[a-zA-Z_][a-zA-Z0-9_]*)   # converter name
        (?:\((?P<args>.*?)\))?                  # converter arguments
        \:                                      # variable delimiter
    )?
    (?P<variable>[a-zA-Z][a-zA-Z0-9_]*)         # variable name
    >
''', re.VERBOSE)


def parse_rule(rule):
    """
    Parse a rule and return it as generator. Each iteration yields tuples in the
    form ``(converter, arguments, variable)``. If the converter is `None` it's a
    static url part, otherwise it's a dynamic one.
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
            raise ValueError('variable name %r used twice.' % variable)
        used_names.add(variable)
        yield converter, data['args'] or None, variable
        pos = m.end()
    if pos < end:
        remaining = rule[pos:]
        if '>' in remaining or '<' in remaining:
            raise ValueError('malformed url rule: %r' % rule)
        yield None, None, remaining


def get_converter(map, name, args):
    """
    Create a new converter for the given arguments or raise
    exception if the converter does not exist.
    """
    if not name in map.converters:
        raise LookupError('the converter %r does not exist' % name)
    if args:
        storage = type('_Storage', (), {'__getitem__': lambda s, x: x})()
        args, kwargs = eval(u'(lambda *a, **kw: (a, kw))(%s)' % args, {}, storage)
    else:
        args = ()
        kwargs = {}
    return map.converters[name](map, *args, **kwargs)


class RoutingException(Exception):
    """
    Special exceptions that require the application to redirect, notifies him
    about missing urls etc.
    """


class RequestRedirect(RoutingException):
    """
    Raise if the map requests a redirect. This is for example the case if
    `strict_slashes` are activated and an url that requires a leading slash.

    The attribute `new_url` contains the absolute desitination url.
    """

    def __init__(self, new_url):
        self.new_url = new_url
        RoutingException.__init__(self, new_url)

    def __call__(self, environ, start_response):
        return redirect(self.new_url)(environ, start_response)


class RequestSlash(RoutingException):
    """
    Internal exception.
    """


class BuildError(RoutingException, LookupError):
    """
    Raised if the build system cannot find a URL for an endpoint with the
    values provided.
    """

    def __init__(self, endpoint, values):
        LookupError.__init__(self, endpoint)
        self.endpoint = endpoint
        self.values = values


class ValidationError(ValueError):
    """
    Validation error.
    """


class RuleFactory(object):
    """
    An object that produces Rules when given a Map.
    """

    def get_rules(self, map):
        raise NotImplementedError()


class Subdomain(RuleFactory):
    """
    Collects rules for a given subdomain.
    """

    def __init__(self, subdomain, rules):
        self.subdomain = subdomain
        self.rules = rules

    def get_rules(self, map):
        for rulefactory in self.rules:
            for rule in rulefactory.get_rules(map):
                rule.subdomain = self.subdomain
                yield rule


class Submount(RuleFactory):
    """
    Collects rules for a given path.
    """

    def __init__(self, path, rules):
        self.path = path.rstrip('/')
        self.rules = rules

    def get_rules(self, map):
        for rulefactory in self.rules:
            for rule in rulefactory.get_rules(map):
                rule.rule = self.path + rule.rule
                yield rule


class EndpointPrefix(RuleFactory):
    """
    Prefixes all endpoints with a given string.
    """

    def __init__(self, prefix, rules):
        self.prefix = prefix
        self.rules = rules

    def get_rules(self, map):
        for rulefactory in self.rules:
            for rule in rulefactory.get_rules(map):
                rule.endpoint = self.prefix + rule.endpoint
                yield rule


class RuleTemplate(object):
    """
    Returns copies of the rules wrapped and expands string templates in
    the endpoint, rule, defaults or subdomain sections.
    """

    def __init__(self, rules):
        self.rules = list(rules)

    def __call__(self, *args, **kwargs):
        return RuleTemplateFactory(self.rules, dict(*args, **kwargs))


class RuleTemplateFactory(RuleFactory):
    """
    A factory that fills in template variables into rules.  Used by
    `RuleTemplate` internally.
    """

    def __init__(self, rules, context):
        self.rules = rules
        self.context = context

    def get_rules(self, map):
        for rulefactory in self.rules:
            for rule in rulefactory.get_rules(map):
                new_defaults = subdomain = None
                if rule.defaults is not None:
                    new_defaults = {}
                    for key, value in rule.defaults.iteritems():
                        if isinstance(value, basestring):
                            value = format_string(value, self.context)
                        new_defaults[key] = value
                if rule.subdomain is not None:
                    subdomain = format_string(rule.subdomain, self.context)
                new_endpoint = rule.endpoint
                if isinstance(new_endpoint, basestring):
                    new_endpoint = format_string(new_endpoint, self.context)
                yield Rule(
                    format_string(rule.rule, self.context),
                    new_defaults,
                    subdomain,
                    rule.methods,
                    rule.build_only,
                    new_endpoint,
                    rule.strict_slashes
                )


class Rule(RuleFactory):
    """
    Represents one url pattern.
    """

    def __init__(self, string, defaults=None, subdomain=None, methods=None,
                 build_only=False, endpoint=None, strict_slashes=None):
        if not string.startswith('/'):
            raise ValueError('urls must start with a leading slash')
        self.rule = string
        self.is_leaf = not string.endswith('/')

        self.map = None
        self.strict_slashes = strict_slashes
        self.subdomain = subdomain
        self.defaults = defaults
        self.build_only = build_only
        if methods is None:
            self.methods = None
        else:
            self.methods = m = []
            for method in methods:
                m.append(method.upper())
            self.methods.sort(lambda a, b: cmp(len(b), len(a)))
        self.endpoint = endpoint
        self.greediness = 0

        self._trace = []
        if defaults is not None:
            self.arguments = set(map(str, defaults))
        else:
            self.arguments = set()
        self._converters = {}
        self._regex = None
        self._weights = []

    def get_rules(self, map):
        yield self

    def bind(self, map):
        """
        Bind the url to a map and create a regular expression based on
        the information from the rule itself and the defaults from the map.
        """
        if self.map is not None:
            raise RuntimeError('url rule %r already bound to map %r' %
                               (self, self.map))
        self.map = map
        if self.strict_slashes is None:
            self.strict_slashes = map.strict_slashes
        if self.subdomain is None:
            self.subdomain = map.default_subdomain

        rule = self.subdomain + '|' + (self.is_leaf and self.rule
                                       or self.rule.rstrip('/'))

        regex_parts = []
        for converter, arguments, variable in parse_rule(rule):
            if converter is None:
                regex_parts.append(re.escape(variable))
                self._trace.append((False, variable))
                self._weights.append(len(variable))
            else:
                convobj = get_converter(map, converter, arguments)
                regex_parts.append('(?P<%s>%s)' % (variable, convobj.regex))
                self._converters[variable] = convobj
                self._trace.append((True, variable))
                self._weights.append(convobj.weight)
                self.arguments.add(str(variable))
                if convobj.is_greedy:
                    self.greediness += 1
        if not self.is_leaf:
            self._trace.append((False, '/'))

        if self.methods is None:
            method_re = '[^>]*'
        else:
            method_re = '|'.join([re.escape(x) for x in self.methods])

        if not self.build_only:
            regex = r'^%s%s\(%s\)$' % (
                u''.join(regex_parts),
                (not self.is_leaf or not self.strict_slashes) and \
                    '(?<!/)(?P<__suffix__>/?)' or '',
                method_re
            )
            self._regex = re.compile(regex, re.UNICODE)

    def match(self, path):
        """
        Check if the rule matches a given path. Path is a string in the
        form ``"subdomain|/path(method)"`` and is assembled by the map.

        If the rule matches a dict with the converted values is returned,
        otherwise the return value is `None`.
        """
        if not self.build_only:
            m = self._regex.search(path)
            if m is not None:
                groups = m.groupdict()
                # we have a folder like part of the url without a trailing
                # slash and strict slashes enabled. raise an exception that
                # tells the map to redirect to the same url but with a
                # trailing slash
                if self.strict_slashes and not self.is_leaf and \
                   not groups.pop('__suffix__'):
                    raise RequestSlash()
                # if we are not in strict slashes mode we have to remove
                # a __suffix__
                elif not self.strict_slashes:
                    del groups['__suffix__']

                result = {}
                for name, value in groups.iteritems():
                    try:
                        value = self._converters[name].to_python(value)
                    except ValidationError:
                        return
                    result[str(name)] = value
                if self.defaults is not None:
                    result.update(self.defaults)
                return result

    def build(self, values):
        """
        Assembles the relative url for that rule and the subdomain.
        If building doesn't work for some reasons `None` is returned.
        """
        tmp = []
        processed = set(self.arguments)
        for is_dynamic, data in self._trace:
            if is_dynamic:
                try:
                    tmp.append(self._converters[data].to_url(values[data]))
                except ValidationError:
                    return
                processed.add(data)
            else:
                tmp.append(data)
        subdomain, url = (u''.join(tmp)).split('|', 1)

        query_vars = {}
        for key in set(values) - processed:
            query_vars[key] = unicode(values[key])
        if query_vars:
            url += '?' + url_encode(query_vars, self.map.charset)

        return subdomain, url

    def provides_defaults_for(self, rule):
        """Check if this rule has defaults for a given rule."""
        return not self.build_only and self.defaults is not None and \
               self.endpoint == rule.endpoint and self != rule and \
               self.arguments == rule.arguments

    def suitable_for(self, values, method):
        """Check if the dict of values has enough data for url generation."""
        if self.methods is not None and method not in self.methods:
            return False

        valueset = set(values)

        for key in self.arguments - set(self.defaults or ()):
            if key not in values:
                return False

        if self.arguments.issubset(valueset):
            if self.defaults is None:
                return True
            for key, value in self.defaults.iteritems():
                if value != values[key]:
                    return False

        return True

    def match_compare(self, other):
        """Compare this object with another one for matching"""
        for sw, ow in izip(self._weights, other._weights):
            if sw > ow:
                return -1
            elif sw < ow:
                return 1        
        if len(self._weights) > len(other._weights):
            return -1
        if not other.arguments and self.arguments:
            return 1
        elif other.arguments and not self.arguments:
            return -1
        elif other.defaults is None and self.defaults is not None:
            return 1
        elif other.defaults is not None and self.defaults is None:
            return -1
        elif self.greediness > other.greediness:
            return -1
        elif self.greediness < other.greediness:
            return 1
        elif len(self.arguments) > len(other.arguments):
            return 1
        elif len(self.arguments) < len(other.arguments):
            return -1
        return 1

    def build_compare(self, other):
        """Compare this object with another one for building."""
        if not other.arguments and self.arguments:
            return -1
        elif other.arguments and not self.arguments:
            return 1
        elif other.defaults is None and self.defaults is not None:
            return -1
        elif other.defaults is not None and self.defaults is None:
            return 1
        elif self.provides_defaults_for(other):
            return -1
        elif other.provides_defaults_for(self):
            return 1
        elif self.greediness > other.greediness:
            return -1
        elif self.greediness < other.greediness:
            return 1
        elif len(self.arguments) > len(other.arguments):
            return -1
        elif len(self.arguments) < len(other.arguments):
            return 1
        return -1

    def __eq__(self, other):
        return self.__class__ is other.__class__ and \
               self._trace == other._trace

    def __ne__(self, other):
        return not self.__eq__(other)

    def __unicode__(self):
        return self.rule

    def __str__(self):
        charset = self.map is not None and self.map.charset or 'utf-8'
        return unicode(self).encode(charset)

    def __repr__(self):
        if self.map is None:
            return '<%s (unbound)>' % self.__class__.__name__
        charset = self.map is not None and self.map.charset or 'utf-8'
        tmp = []
        for is_dynamic, data in self._trace:
            if is_dynamic:
                tmp.append('<%s>' % data)
            else:
                tmp.append(data)
        return '<%s %r%s -> %s>' % (
            self.__class__.__name__,
            (u''.join(tmp).encode(charset)).lstrip('|'),
            self.methods is not None and ' (%s)' % \
                ', '.join(self.methods) or '',
            self.endpoint
        )


class BaseConverter(object):
    """
    Base class for all converters.
    """
    regex = '[^/]+'
    is_greedy = False
    weight = 100

    def __init__(self, map):
        self.map = map

    def to_python(self, value):
        return value

    def to_url(self, value):
        return quote(unicode(value).encode(self.map.charset))


class UnicodeConverter(BaseConverter):
    """
    The default converter for all URL parts. Matches one string without a
    slash in the part. Can also check for the length of that string.
    """

    def __init__(self, map, minlength=1, maxlength=None, length=None):
        BaseConverter.__init__(self, map)
        if length is not None:
            length = '{%d}' % int(length)
        else:
            if maxlength is None:
                maxlength = ''
            else:
                maxlength = int(maxlength)
            length = '{%s,%s}' % (
                int(minlength),
                maxlength
            )
        self.regex = '[^/]' + length


class AnyConverter(BaseConverter):
    """
    Matches multiple items from a given set.
    """

    def __init__(self, map, *items):
        BaseConverter.__init__(self, map)
        self.regex = '(?:%s)' % '|'.join([re.escape(x) for x in items])


class PathConverter(BaseConverter):
    """
    Matches a whole path (including slashes)
    """
    regex = '[^/].*?'
    is_greedy = True
    weight = 50


class NumberConverter(BaseConverter):
    """
    Baseclass for `IntegerConverter` and `FloatConverter`.
    """

    def __init__(self, map, fixed_digits=0, min=None, max=None):
        BaseConverter.__init__(self, map)
        self.fixed_digits = fixed_digits
        self.min = min
        self.max = max

    def to_python(self, value):
        if (self.fixed_digits and len(value) != self.fixed_digits):
            raise ValidationError()
        value = self.num_convert(value)
        if (self.min is not None and value < self.min) or \
           (self.max is not None and value > self.max):
            raise ValidationError()
        return value

    def to_url(self, value):
        value = self.num_convert(value)
        if self.fixed_digits:
            value = ('%%0%sd' % self.fixed_digits) % value
        return str(value)


class IntegerConverter(NumberConverter):
    """
    Only accepts integers.
    """
    regex = r'\d+'
    num_convert = int


class FloatConverter(NumberConverter):
    """
    Only accepts floats and integers.
    """
    regex = r'\d+\.\d+'
    num_convert = float

    def __init__(self, map, min=None, max=None):
        NumberConverter.__init__(self, map, 0, min, max)


class Map(object):
    """
    The base class for all the url maps.
    """

    def __init__(self, rules=None, default_subdomain='', charset='utf-8',
                 strict_slashes=True, redirect_defaults=True,
                 converters=None):
        """
        `rules`
            sequence of url rules for this map.

        `default_subdomain`
            The default subdomain for rules without a subdomain defined.

        `charset`
            charset of the url. defaults to ``"utf-8"``

        `strict_slashes`
            Take care of trailing slashes.

        `redirect_defaults`
            This will redirect to the default rule if it wasn't visited
            that way. This helps creating unique urls.

        `converters`
            A dict of converters that adds additional converters to the
            list of converters. If you redefine one converter this will
            override the original one.
        """
        self._rules = []
        self._rules_by_endpoint = {}
        self._remap = True

        self.default_subdomain = default_subdomain
        self.charset = charset
        self.strict_slashes = strict_slashes
        self.redirect_defaults = redirect_defaults

        self.converters = DEFAULT_CONVERTERS.copy()
        if converters:
            self.converters.update(converters)

        for rulefactory in rules or ():
            self.add(rulefactory)

    def is_endpoint_expecting(self, endpoint, *arguments):
        """
        Iterate over all rules and check if the endpoint expects
        the arguments provided.  This is for example useful if you have
        some URLs that expect a language code and others that do not and
        you want to wrap the builder a bit so that the current language
        code is automatically added if not provided but endpoints expect
        it.
        """
        self.update()
        arguments = set(arguments)
        for rule in self._rules_by_endpoint[endpoint]:
            if arguments.issubset(rule.arguments):
                return True
        return False

    def iter_rules(self, endpoint=None):
        """Iterate over all rules or the rules of an endpoint."""
        if endpoint is not None:
            return iter(self._rules_by_endpoint[endpoint])
        return iter(self._rules)

    def add(self, rulefactory):
        """
        Add a new rule or factory to the map and bind it.  Requires that the
        rule is not bound to another map.
        """
        for rule in rulefactory.get_rules(self):
            rule.bind(self)
            self._rules.append(rule)
            self._rules_by_endpoint.setdefault(rule.endpoint, []).append(rule)
        self._remap = True

    def add_rule(self, rule):
        from warnings import warn
        warn(DeprecationWarning('use map.add instead of map.add_rule now'))
        return self.add(rule)

    def bind(self, server_name, script_name=None, subdomain=None,
             url_scheme='http', default_method='GET'):
        """
        Return a new map adapter for this request.
        """
        if subdomain is None:
            subdomain = self.default_subdomain
        if script_name is None:
            script_name = '/'
        return MapAdapter(self, server_name, script_name, subdomain,
                          url_scheme, default_method)

    def bind_to_environ(self, environ, server_name=None, subdomain=None,
                        calculate_subdomain=False):
        """
        Like `bind` but the required information are pulled from the
        WSGI environment provided where possible. For some information
        this won't work (subdomains), if you want that feature you have
        to provide the subdomain with the `subdomain` variable.

        If `subdomain` is `None` but an environment and a server name is
        provided it will calculate the current subdomain automatically.
        Example: `server_name` is ``'example.com'`` and the `SERVER_NAME`
        in the wsgi `environ` is ``'staging.dev.example.com'`` the calculated
        subdomain will be ``'staging.dev'``.
        """
        if server_name is None:
            if 'HTTP_HOST' in environ:
                server_name = environ['HTTP_HOST']
            else:
                server_name = environ['SERVER_NAME']
                if (environ['wsgi.url_scheme'], environ['SERVER_PORT']) not \
                   in (('https', '443'), ('http', '80')):
                    server_name += ':' + environ['SERVER_PORT']
        elif subdomain is None:
            cur_server_name = environ['SERVER_NAME'].split('.')
            real_server_name = server_name.split(':', 1)[0].split('.')
            offset = -len(real_server_name)
            if cur_server_name[offset:] != real_server_name:
                raise ValueError('the server name provided (%r) does not match the '
                                 'server name from the WSGI environment (%r)' %
                                 (environ['SERVER_NAME'], server_name))
            subdomain = '.'.join(filter(None, cur_server_name[:offset]))
        return Map.bind(self, server_name, environ.get('SCRIPT_NAME'), subdomain,
                        environ['wsgi.url_scheme'], environ['REQUEST_METHOD'])

    def update(self):
        """
        Called before matching and building to keep the compiled rules
        in the correct order after things changed.
        """
        if self._remap:
            self._rules.sort(lambda a, b: a.match_compare(b))
            for rules in self._rules_by_endpoint.itervalues():
                rules.sort(lambda a, b: a.build_compare(b))
            self._remap = False


class MapAdapter(object):
    """
    Retured by `Map.bind` or `Map.bind_to_environ` and does the
    URL matching and building based on runtime information.
    """

    def __init__(self, map, server_name, script_name, subdomain,
                 url_scheme, default_method):
        self.map = map
        self.server_name = server_name
        if not script_name.endswith('/'):
            script_name += '/'
        self.script_name = script_name
        self.subdomain = subdomain
        self.url_scheme = url_scheme
        self.default_method = default_method

    def dispatch(self, view_func, path_info, method=None):
        """
        Does the complete dispatching process.  `view_func` is called with
        the endpoint and a dict with the values for the view.  It should
        look up the view function, call it, and return a response object
        or WSGI application.  http exceptions are not catched.
        """
        try:
            endpoint, args = self.match(path_info, method)
        except RequestRedirect, e:
            return e
        return view_func(endpoint, args)

    def match(self, path_info, method=None):
        """
        Match a given path_info, script_name and subdomain against the
        known rules. If the subdomain is not given it defaults to the
        default subdomain of the map which is usally `www`. Thus if you
        don't define it anywhere you can safely ignore it.
        """
        self.map.update()
        if not isinstance(path_info, unicode):
            path_info = path_info.decode(self.map.charset, 'ignore')
        path = u'%s|/%s(%s)' % (
            self.subdomain,
            path_info.lstrip('/'),
            (method or self.default_method).upper()
        )
        for rule in self.map._rules:
            try:
                rv = rule.match(path)
            except RequestSlash:
                raise RequestRedirect(str('%s://%s%s%s/%s/' % (
                    self.url_scheme,
                    self.subdomain and self.subdomain + '.' or '',
                    self.server_name,
                    self.script_name[:-1],
                    path_info.lstrip('/')
                )))
            if rv is None:
                continue
            if self.map.redirect_defaults:
                for r in self.map._rules_by_endpoint[rule.endpoint]:
                    if r.provides_defaults_for(rule) and \
                       r.suitable_for(rv, method):
                        rv.update(r.defaults)
                        subdomain, path = r.build(rv)
                        raise RequestRedirect(str('%s://%s%s%s/%s' % (
                            self.url_scheme,
                            subdomain and subdomain + '.' or '',
                            self.server_name,
                            self.script_name[:-1],
                            path.lstrip('/')
                        )))
            return rule.endpoint, rv
        raise NotFound()

    def build(self, endpoint, values=None, method=None, force_external=False):
        """
        Build a new url hostname relative to the current one. If you
        reference a resource on another subdomain the hostname is added
        automatically. You can force external urls by setting
        `force_external` to `True`.
        """
        self.map.update()
        method = method or self.default_method
        if values:
            values = dict([(k, v) for k, v in values.items() if v is not None])
        else:
            values = {}

        for rule in self.map._rules_by_endpoint.get(endpoint) or ():
            if rule.suitable_for(values, method):
                rv = rule.build(values)
                if rv is not None:
                    break
        else:
            raise BuildError(endpoint, values)
        subdomain, path = rv
        if not force_external and subdomain == self.subdomain:
            return str(urljoin(self.script_name, path.lstrip('/')))
        return str('%s://%s%s%s/%s' % (
            self.url_scheme,
            subdomain and subdomain + '.' or '',
            self.server_name,
            self.script_name[:-1],
            path.lstrip('/')
        ))


DEFAULT_CONVERTERS = {
    'default':          UnicodeConverter,
    'string':           UnicodeConverter,
    'any':              AnyConverter,
    'path':             PathConverter,
    'int':              IntegerConverter,
    'float':            FloatConverter
}
