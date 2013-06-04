# -*- coding: utf-8 -*-
"""
    werkzeug._internal
    ~~~~~~~~~~~~~~~~~~

    This module provides internally used helpers and constants.

    :copyright: (c) 2013 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import string
import inspect
from weakref import WeakKeyDictionary
from datetime import datetime, date

from werkzeug._compat import integer_types, iter_bytes, text_type, BytesIO


_logger = None
_empty_stream = BytesIO()
_signature_cache = WeakKeyDictionary()
_epoch_ord = date(1970, 1, 1).toordinal()
_cookie_params = set((b'expires', b'path', b'comment',
                      b'max-age', b'secure', b'httponly',
                      b'version'))
_legal_cookie_chars = set(iter_bytes((string.ascii_letters +
                                      string.digits +
                                      u"!#$%&'*+-.^_`|~:").encode('ascii')))

_cookie_quoting_map = {
    b'\000' : b'\\000',  b'\001' : b'\\001',  b'\002' : b'\\002',
    b'\003' : b'\\003',  b'\004' : b'\\004',  b'\005' : b'\\005',
    b'\006' : b'\\006',  b'\007' : b'\\007',  b'\010' : b'\\010',
    b'\011' : b'\\011',  b'\012' : b'\\012',  b'\013' : b'\\013',
    b'\014' : b'\\014',  b'\015' : b'\\015',  b'\016' : b'\\016',
    b'\017' : b'\\017',  b'\020' : b'\\020',  b'\021' : b'\\021',
    b'\022' : b'\\022',  b'\023' : b'\\023',  b'\024' : b'\\024',
    b'\025' : b'\\025',  b'\026' : b'\\026',  b'\027' : b'\\027',
    b'\030' : b'\\030',  b'\031' : b'\\031',  b'\032' : b'\\032',
    b'\033' : b'\\033',  b'\034' : b'\\034',  b'\035' : b'\\035',
    b'\036' : b'\\036',  b'\037' : b'\\037',

    # Because of the way browsers really handle cookies (as opposed
    # to what the RFC says) we also encode , and ;

    b',' : b'\\054', b';' : b'\\073',

    b'"' : b'\\"',       b'\\' : b'\\\\',

    b'\177' : b'\\177',  b'\200' : b'\\200',  b'\201' : b'\\201',
    b'\202' : b'\\202',  b'\203' : b'\\203',  b'\204' : b'\\204',
    b'\205' : b'\\205',  b'\206' : b'\\206',  b'\207' : b'\\207',
    b'\210' : b'\\210',  b'\211' : b'\\211',  b'\212' : b'\\212',
    b'\213' : b'\\213',  b'\214' : b'\\214',  b'\215' : b'\\215',
    b'\216' : b'\\216',  b'\217' : b'\\217',  b'\220' : b'\\220',
    b'\221' : b'\\221',  b'\222' : b'\\222',  b'\223' : b'\\223',
    b'\224' : b'\\224',  b'\225' : b'\\225',  b'\226' : b'\\226',
    b'\227' : b'\\227',  b'\230' : b'\\230',  b'\231' : b'\\231',
    b'\232' : b'\\232',  b'\233' : b'\\233',  b'\234' : b'\\234',
    b'\235' : b'\\235',  b'\236' : b'\\236',  b'\237' : b'\\237',
    b'\240' : b'\\240',  b'\241' : b'\\241',  b'\242' : b'\\242',
    b'\243' : b'\\243',  b'\244' : b'\\244',  b'\245' : b'\\245',
    b'\246' : b'\\246',  b'\247' : b'\\247',  b'\250' : b'\\250',
    b'\251' : b'\\251',  b'\252' : b'\\252',  b'\253' : b'\\253',
    b'\254' : b'\\254',  b'\255' : b'\\255',  b'\256' : b'\\256',
    b'\257' : b'\\257',  b'\260' : b'\\260',  b'\261' : b'\\261',
    b'\262' : b'\\262',  b'\263' : b'\\263',  b'\264' : b'\\264',
    b'\265' : b'\\265',  b'\266' : b'\\266',  b'\267' : b'\\267',
    b'\270' : b'\\270',  b'\271' : b'\\271',  b'\272' : b'\\272',
    b'\273' : b'\\273',  b'\274' : b'\\274',  b'\275' : b'\\275',
    b'\276' : b'\\276',  b'\277' : b'\\277',  b'\300' : b'\\300',
    b'\301' : b'\\301',  b'\302' : b'\\302',  b'\303' : b'\\303',
    b'\304' : b'\\304',  b'\305' : b'\\305',  b'\306' : b'\\306',
    b'\307' : b'\\307',  b'\310' : b'\\310',  b'\311' : b'\\311',
    b'\312' : b'\\312',  b'\313' : b'\\313',  b'\314' : b'\\314',
    b'\315' : b'\\315',  b'\316' : b'\\316',  b'\317' : b'\\317',
    b'\320' : b'\\320',  b'\321' : b'\\321',  b'\322' : b'\\322',
    b'\323' : b'\\323',  b'\324' : b'\\324',  b'\325' : b'\\325',
    b'\326' : b'\\326',  b'\327' : b'\\327',  b'\330' : b'\\330',
    b'\331' : b'\\331',  b'\332' : b'\\332',  b'\333' : b'\\333',
    b'\334' : b'\\334',  b'\335' : b'\\335',  b'\336' : b'\\336',
    b'\337' : b'\\337',  b'\340' : b'\\340',  b'\341' : b'\\341',
    b'\342' : b'\\342',  b'\343' : b'\\343',  b'\344' : b'\\344',
    b'\345' : b'\\345',  b'\346' : b'\\346',  b'\347' : b'\\347',
    b'\350' : b'\\350',  b'\351' : b'\\351',  b'\352' : b'\\352',
    b'\353' : b'\\353',  b'\354' : b'\\354',  b'\355' : b'\\355',
    b'\356' : b'\\356',  b'\357' : b'\\357',  b'\360' : b'\\360',
    b'\361' : b'\\361',  b'\362' : b'\\362',  b'\363' : b'\\363',
    b'\364' : b'\\364',  b'\365' : b'\\365',  b'\366' : b'\\366',
    b'\367' : b'\\367',  b'\370' : b'\\370',  b'\371' : b'\\371',
    b'\372' : b'\\372',  b'\373' : b'\\373',  b'\374' : b'\\374',
    b'\375' : b'\\375',  b'\376' : b'\\376',  b'\377' : b'\\377'
}


_octal_re = re.compile(b'\\\\[0-3][0-7][0-7]')
_quote_re = re.compile(b'[\\\\].')
_legal_cookie_chars_re = b'[\w\d!#%&\'~_`><@,:/\$\*\+\-\.\^\|\)\(\?\}\{\=]'
_cookie_re = re.compile(b"""
    (?x)                                    # This is a verbose pattern
    (?P<key>                                # Start of group 'key'
    """ + _legal_cookie_chars_re + b"""+?   # Any word of at least one letter
    )                                       # End of group 'key'
    \s*=\s*                                 # Equal Sign
    (?P<val>                                # Start of group 'val'
    "(?:[^\\\\"]|\\\\.)*"                   # Any doublequoted string
    |                                       # or
    \w{3},\s[\w\d\s-]{9,11}\s[\d:]{8}\sGMT  # Special case for "expires" attr
    |                                       # or
    """ + _legal_cookie_chars_re + b"""*    # Any word or empty string
    )                                       # End of group 'val'
    \s*;?                                   # Probably ending in a semi-colon
""")


class _Missing(object):

    def __repr__(self):
        return 'no value'

    def __reduce__(self):
        return '_missing'

_missing = _Missing()


def _get_environ(obj):
    env = getattr(obj, 'environ', obj)
    assert isinstance(env, dict), \
        '%r is not a WSGI environment (has to be a dict)' % type(obj).__name__
    return env


def _log(type, message, *args, **kwargs):
    """Log into the internal werkzeug logger."""
    global _logger
    if _logger is None:
        import logging
        _logger = logging.getLogger('werkzeug')
        # Only set up a default log handler if the
        # end-user application didn't set anything up.
        if not logging.root.handlers and _logger.level == logging.NOTSET:
            _logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            _logger.addHandler(handler)
    getattr(_logger, type)(message.rstrip(), *args, **kwargs)


def _parse_signature(func):
    """Return a signature object for the function."""
    if hasattr(func, 'im_func'):
        func = func.im_func

    # if we have a cached validator for this function, return it
    parse = _signature_cache.get(func)
    if parse is not None:
        return parse

    # inspect the function signature and collect all the information
    positional, vararg_var, kwarg_var, defaults = inspect.getargspec(func)
    defaults = defaults or ()
    arg_count = len(positional)
    arguments = []
    for idx, name in enumerate(positional):
        if isinstance(name, list):
            raise TypeError('cannot parse functions that unpack tuples '
                            'in the function signature')
        try:
            default = defaults[idx - arg_count]
        except IndexError:
            param = (name, False, None)
        else:
            param = (name, True, default)
        arguments.append(param)
    arguments = tuple(arguments)

    def parse(args, kwargs):
        new_args = []
        missing = []
        extra = {}

        # consume as many arguments as positional as possible
        for idx, (name, has_default, default) in enumerate(arguments):
            try:
                new_args.append(args[idx])
            except IndexError:
                try:
                    new_args.append(kwargs.pop(name))
                except KeyError:
                    if has_default:
                        new_args.append(default)
                    else:
                        missing.append(name)
            else:
                if name in kwargs:
                    extra[name] = kwargs.pop(name)

        # handle extra arguments
        extra_positional = args[arg_count:]
        if vararg_var is not None:
            new_args.extend(extra_positional)
            extra_positional = ()
        if kwargs and not kwarg_var is not None:
            extra.update(kwargs)
            kwargs = {}

        return new_args, kwargs, missing, extra, extra_positional, \
               arguments, vararg_var, kwarg_var
    _signature_cache[func] = parse
    return parse


def _date_to_unix(arg):
    """Converts a timetuple, integer or datetime object into the seconds from
    epoch in utc.
    """
    if isinstance(arg, datetime):
        arg = arg.utctimetuple()
    elif isinstance(arg, (int, long, float)):
        return int(arg)
    year, month, day, hour, minute, second = arg[:6]
    days = date(year, month, 1).toordinal() - _epoch_ord + day - 1
    hours = days * 24 + hour
    minutes = hours * 60 + minute
    seconds = minutes * 60 + second
    return seconds


class _DictAccessorProperty(object):
    """Baseclass for `environ_property` and `header_property`."""
    read_only = False

    def __init__(self, name, default=None, load_func=None, dump_func=None,
                 read_only=None, doc=None):
        self.name = name
        self.default = default
        self.load_func = load_func
        self.dump_func = dump_func
        if read_only is not None:
            self.read_only = read_only
        self.__doc__ = doc

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        storage = self.lookup(obj)
        if self.name not in storage:
            return self.default
        rv = storage[self.name]
        if self.load_func is not None:
            try:
                rv = self.load_func(rv)
            except (ValueError, TypeError):
                rv = self.default
        return rv

    def __set__(self, obj, value):
        if self.read_only:
            raise AttributeError('read only property')
        if self.dump_func is not None:
            value = self.dump_func(value)
        self.lookup(obj)[self.name] = value

    def __delete__(self, obj):
        if self.read_only:
            raise AttributeError('read only property')
        self.lookup(obj).pop(self.name, None)

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.name
        )


def _cookie_quote(b):
    buf = bytearray()
    all_legal = True
    _lookup = _cookie_quoting_map.get
    _push = buf.extend

    for char in iter_bytes(b):
        if char not in _legal_cookie_chars:
            all_legal = False
            _push(_lookup(char, char))
        else:
            _push(char)

    if all_legal:
        return bytes(buf)
    return bytes(b'"' + buf + b'"')


def _cookie_unquote(b):
    if len(b) < 2:
        return b
    if b[:1] != b'"' or b[-1:] != b'"':
        return b

    b = b[1:-1]

    i = 0
    n = len(b)
    rv = bytearray()
    _push = rv.extend

    while 0 <= i < n:
        o_match = _octal_re.search(b, i)
        q_match = _quote_re.search(b, i)
        if not o_match and not q_match:
            rv.extend(b[i:])
            break
        j = k = -1
        if o_match:
            j = o_match.start(0)
        if q_match:
            k = q_match.start(0)
        if q_match and (not o_match or k < j):
            _push(b[i:k])
            _push(b[k + 1])
            i = k + 2
        else:
            _push(b[i:j])
            rv.append(int(b[j + 1:j + 4], 8))
            i = j + 4

    return bytes(rv)


def _cookie_parse_impl(b):
    """Lowlevel cookie parsing facility that operates on bytes."""
    i = 0
    n = len(b)

    while 0 <= i < n:
        match = _cookie_re.search(b, i)
        if not match:
            break

        key = match.group('key')
        value = match.group('val')
        i = match.end(0)

        # Ignore parameters.  We have no interest in them.
        if key.lower() not in _cookie_params:
            yield _cookie_unquote(key), _cookie_unquote(value)


def _make_cookie_domain(domain):
    if domain is None:
        return None

    if isinstance(domain, text_type):
        domain = domain.encode('idna')

    # The port part of the domain should NOT be used. Strip it
    if b':' in domain:
        domain = domain.split(b':', 1)[0]

    if b'.' in domain:
        return domain

    raise ValueError(
        'Setting \'domain\' for a cookie on a server running localy (ex: '
        'localhost) is not supportted by complying browsers. You should '
        'have something like: \'127.0.0.1 localhost dev.localhost\' on '
        'your hosts file and then point your server to run on '
        '\'dev.localhost\' and also set \'domain\' for \'dev.localhost\''
    )


def _easteregg(app=None):
    """Like the name says.  But who knows how it works?"""
    def bzzzzzzz(gyver):
        import base64
        import zlib
        return zlib.decompress(base64.b64decode(gyver)).decode('ascii')
    gyver = u'\n'.join([x + (77 - len(x)) * u' ' for x in bzzzzzzz(b'''
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
7f2zLkGNv8b191cD/3vs9Q833z8t''').splitlines()])
    def easteregged(environ, start_response):
        def injecting_start_response(status, headers, exc_info=None):
            headers.append(('X-Powered-By', 'Werkzeug'))
            return start_response(status, headers, exc_info)
        if app is not None and environ.get('QUERY_STRING') != 'macgybarchakku':
            return app(environ, injecting_start_response)
        injecting_start_response('200 OK', [('Content-Type', 'text/html')])
        return [(u'''
<!DOCTYPE html>
<html>
<head>
<title>About Werkzeug</title>
<style type="text/css">
  body { font: 15px Georgia, serif; text-align: center; }
  a { color: #333; text-decoration: none; }
  h1 { font-size: 30px; margin: 20px 0 10px 0; }
  p { margin: 0 0 30px 0; }
  pre { font: 11px 'Consolas', 'Monaco', monospace; line-height: 0.95; }
</style>
</head>
<body>
<h1><a href="http://werkzeug.pocoo.org/">Werkzeug</a></h1>
<p>the Swiss Army knife of Python web development.</p>
<pre>%s\n\n\n</pre>
</body>
</html>''' % gyver).encode('latin1')]
    return easteregged
