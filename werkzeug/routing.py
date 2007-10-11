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

from werkzeug.utils import url_encode
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


def get_converter(map, name, args, frame):
    """
    Create a new converter for the given arguments or raise
    exception if the converter does not exist.
    """
    if not name in map.converters:
        raise LookupError('the converter %r does not exist' % name)
    if args:
        args, kwargs = eval('(lambda *a, **kw: (a, kw))(%s)' % args,
                            frame.f_globals, frame.f_locals)
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


class RequestSlash(RoutingException):
    """
    Internal exception.
    """


class NotFound(RoutingException, ValueError):
    """
    Raise if there is no match for the current url.
    """


class ValidationError(ValueError):
    """
    Validation error.
    """


class RuleFactory(object):
    """
    An object that produces Rules when given a Map.
    """

    def get_rules(self, map):
        raise NotImplementedError


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


class Rule(RuleFactory):
    """
    Represents one url pattern.
    """

    def __init__(self, string, defaults=None, subdomain=None, methods=None,
                 build_only=False, endpoint=None, strict_slashes=None):
        if not string.startswith('/'):
            raise ValueError('urls must start with a leading slash')
        if string.endswith('/'):
            self.is_leaf = False
            string = string.rstrip('/')
        else:
            self.is_leaf = True
        self.rule = unicode(string)

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

        self._trace = []
        if defaults is not None:
            self.arguments = set(map(str, defaults))
        else:
            self.arguments = set()
        self._converters = {}
        self._regex = None

        self._frame = sys._getframe(1)

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

        rule = self.subdomain + '|' + self.rule

        regex_parts = []
        for converter, arguments, variable in parse_rule(rule):
            if converter is None:
                regex_parts.append(re.escape(variable))
                self._trace.append((False, variable))
            else:
                convobj = get_converter(map, converter, arguments,
                                        self._frame)
                regex_parts.append('(?P<%s>%s)' % (variable, convobj.regex))
                self._converters[variable] = convobj
                self._trace.append((True, variable))
                self.arguments.add(str(variable))
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
        self._frame = None

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
        """
        Check if this rule is defaults for a given rule.
        """
        return not self.build_only and self.defaults is not None and \
               self.endpoint == rule.endpoint and self != rule and \
               self.arguments == rule.arguments

    def suitable_for(self, values):
        """
        Check if the dict of values contains enough data for url generation.
        """
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
        # XXX: make this more robust
        def calc(obj):
            rv = len(obj.arguments)
            # although defaults variables are already in the arguments
            # we add them a second time to the complexity to push the
            # rule.
            if obj.defaults is not None:
                rv += len(obj.defaults) + 2
            # push leafs
            if obj.is_leaf:
                rv += 2
            return -rv
        return cmp(calc(self), calc(other))

    def build_compare(self, other):
        """Compare this object with another one for building."""
        if not other.arguments and self.arguments:
            return -1
        if other.defaults is None and self.defaults is not None:
            return 1
        if self.provides_defaults_for(other):
            return 1
        if len(self.arguments) < len(other.arguments):
            return 1
        return -1

    def __eq__(self, other):
        return self.__class__ is other.__class__ and \
               self._trace == other._trace

    def __ne__(self, other):
        return not self.__eq__(other)

    def __unicode__(self):
        rule = self.rule
        if not self.is_leaf:
            rule += u'/'
        return rule

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
        return '<%s %r -> %s>' % (
            self.__class__.__name__,
            (u''.join(tmp).encode(charset)).lstrip('|'),
            self.endpoint
        )


class BaseConverter(object):
    """
    Base class for all converters.
    """
    regex = '[^/]+'

    def __init__(self, map):
        self.map = map

    def to_python(self, value):
        return value

    def to_url(self, value):
        return quote(unicode(value).encode(self.map.charset))

    def js_to_url_function(self):
        if hasattr(self, '_js_to_url'):
            return u'(function(value) { %s })' % self._js_to_url()
        else:
            return u'encodeURIComponent'


class UnicodeConverter(BaseConverter):
    """
    The default converter for all URL parts. Matches one string without a
    slash in the part. Can also check for the length of that string.
    """

    def __init__(self, map, minlength=1, maxlength=None, length=None):
        super(UnicodeConverter, self).__init__(map)
        if length is not None:
            length = '{%s}' % length
        else:
            if maxlength is None:
                maxlength = ''
            length = '{%s,%s}' % (
                minlength,
                maxlength
            )
        self.regex = '[^/]' + length


class PathConverter(BaseConverter):
    """
    Matches a whole path (including slashes)
    """
    regex = '[^/].*'


class NumberConverter(BaseConverter):
    """
    Baseclass for `IntegerConverter` and `FloatConverter`.
    """

    def __init__(self, map, fixed_digits=0, min=None, max=None):
        super(NumberConverter, self).__init__(map)
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

    def _js_to_url(self):
        if self.fixed_digits:
            return u'''\
var result = value.toString();
while (result.length < %s) {
    result = '0' + result;
}
return result;''' % self.fixed_digits
        else:
            return u'return value.toString();'


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


class Map(object):
    """
    The base class for all the url maps.
    """

    def __init__(self, rules=None, default_subdomain='', charset='ascii',
                 strict_slashes=True, redirect_defaults=True,
                 converters=None):
        """
        `rules`
            sequence of url rules for this map.

        `default_subdomain`
            The default subdomain for rules without a subdomain defined.

        `charset`
            charset of the url. defaults to ``"ascii"``

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
            for rule in rulefactory.get_rules(self):
                self.add_rule(rule)

    def add_rule(self, rule):
        """
        Add a new rule to the map and bind it. Requires that the rule is
        not bound to another map. After adding new rules you have to call
        the `remap` method.
        """
        if not isinstance(rule, Rule):
            raise TypeError('rule objects required')
        rule.bind(self)
        self._rules.append(rule)
        self._rules_by_endpoint.setdefault(rule.endpoint, []).append(rule)
        self._remap = True

    def bind(self, server_name, script_name=None, subdomain=None,
             url_scheme='http'):
        """
        Return a new map adapter for this request.
        """
        if subdomain is None:
            subdomain = self.default_subdomain
        if script_name is None:
            script_name = '/'
        return MapAdapter(self, server_name, script_name, subdomain,
                          url_scheme)

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
                        environ['wsgi.url_scheme'])

    def generate_javascript(self, name='url_map'):
        """
        Generates a JavaScript function containing the rules defined in
        this map, to be used with a MapAdapter's generate_javascript
        method.  If you don't pass a name the returned JavaScript code is
        an expression that returns a function.  Otherwise it's a standalone
        script that assigns the function with that name.  Dotted names are
        resolved (so you an use a name like 'obj.url_for')

        In order to use JavaScript generation, simplejson must be installed.

        Note that using this feature will expose the rules
        defined in your map to users. If your rules contain sensitive
        information, don't use JavaScript generation!
        """
        import simplejson
        from werkzeug.minitmpl import Template
        from werkzeug.constants import JAVASCRIPT_ROUTING

        self.update()
        rules = []
        converters = []
        for rule in self._rules:
            trace = [{u'is_dynamic': is_dynamic, u'data': data} for is_dynamic, data in rule._trace]
            rule_converters = {}
            for key, converter in rule._converters.iteritems():
                js_func = converter.js_to_url_function()
                try:
                    index = converters.index(js_func)
                except ValueError:
                    converters.append(js_func)
                    index = len(converters) - 1
                rule_converters[key] = index
            rules.append({
                u'endpoint': rule.endpoint,
                u'arguments': list(rule.arguments),
                u'converters': rule_converters,
                u'trace': trace,
                u'defaults': rule.defaults
            })

        return Template(JAVASCRIPT_ROUTING).render({
            'name_parts':   name and name.split('.') or [],
            'rules':        simplejson.dumps(rules),
            'converters':   converters
        })

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
                 url_scheme):
        self.map = map
        self.server_name = server_name
        if not script_name.endswith('/'):
            script_name += '/'
        self.script_name = script_name
        self.subdomain = subdomain
        self.url_scheme = url_scheme

    def match(self, path_info, method='GET'):
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
            method.upper()
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
                       r.suitable_for(rv):
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
        raise NotFound(path_info)

    def build(self, endpoint, values=None, force_external=False):
        """
        Build a new url hostname relative to the current one. If you
        reference a resource on another subdomain the hostname is added
        automatically. You can force external urls by setting
        `force_external` to `True`.
        """
        self.map.update()
        values = values or {}

        for rule in self.map._rules_by_endpoint.get(endpoint) or ():
            if rule.suitable_for(values):
                rv = rule.build(values)
                if rv is not None:
                    break
        else:
            raise NotFound(endpoint, values)
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

    def generate_javascript(self, name='url_for', map_name='url_map'):
        """
        Generates JavaScript that calls the function generated by
        Map.generate_javascript with this adapter's arguments.
        """
        import simplejson
        values = {
            u'server_name': simplejson.dumps(self.server_name),
            u'script_name': simplejson.dumps(self.script_name),
            u'subdomain': simplejson.dumps(self.subdomain),
            u'url_scheme': simplejson.dumps(self.url_scheme),
            u'name': name,
            u'map_name': map_name
        }
        return u'''\
var %(name)s = %(map_name)s(
    %(server_name)s, %(script_name)s, %(subdomain)s, %(url_scheme)s
);''' % values


DEFAULT_CONVERTERS = {
    'default':          UnicodeConverter,
    'string':           UnicodeConverter,
    'path':             PathConverter,
    'int':              IntegerConverter,
    'float':            FloatConverter
}
