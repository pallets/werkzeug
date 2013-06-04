# -*- coding: utf-8 -*-
"""
    werkzeug._cookies
    ~~~~~~~~~~~~~~~~~

    A fork of the stdlib's cookie parser with a ton of cleanup.  This is
    necessary because various versions of the library do different things
    but none are doing the correct one :(

    :copyright: (c) 2013 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import string

from werkzeug._compat import iter_bytes, text_type


_reserved_params = set((b'expires', b'path', b'comment',
                        b'max-age', b'secure', b'httponly',
                        b'version'))

_legal_chars = set(iter_bytes((string.ascii_letters +
                               string.digits +
                               u"!#$%&'*+-.^_`|~:").encode('ascii')))

_translation_map = {
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


def _quote(b):
    buf = bytearray()
    all_legal = True
    _lookup = _translation_map.get
    _push = buf.extend

    for char in iter_bytes(b):
        if char not in _legal_chars:
            all_legal = False
            _push(_lookup(char, char))
        else:
            _push(char)

    if all_legal:
        return bytes(buf)
    return bytes(b'"' + buf + b'"')


def _unquote(b):
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


_legal_chars_re  = b'[\w\d!#%&\'~_`><@,:/\$\*\+\-\.\^\|\)\(\?\}\{\=]'
_cookie_re = re.compile(b"""
    (?x)                           # This is a verbose pattern
    (?P<key>                       # Start of group 'key'
    """ + _legal_chars_re + b"""+?   # Any word of at least one letter
    )                              # End of group 'key'
    \s*=\s*                        # Equal Sign
    (?P<val>                       # Start of group 'val'
    "(?:[^\\\\"]|\\\\.)*"                # Any doublequoted string
    |                                # or
    \w{3},\s[\w\d\s-]{9,11}\s[\d:]{8}\sGMT  # Special case for "expires" attr
    |                                # or
    """ + _legal_chars_re + b"""*    # Any word or empty string
    )                              # End of group 'val'
    \s*;?                          # Probably ending in a semi-colon
""")


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
        if key.lower() not in _reserved_params:
            yield _unquote(key), _unquote(value)


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
