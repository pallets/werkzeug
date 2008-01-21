# -*- coding: utf-8 -*-
"""
    werkzeug.useragents
    ~~~~~~~~~~~~~~~~~~~

    This module provides a helper to inspect user agent strings.  This module
    is far from complete but should work for most of the current browsers that
    are available.


    :copyright: 2007-2008 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import re


class UserAgentParser(object):
    """
    A simple user agent parser.
    """
    platforms = [(re.compile(regex, re.I), name) for regex, name in (
        (r'darwin|mac|os\s*x', 'macos'),
        ('win', 'windows'),
        (r'x11|lin(\b|ux)?', 'linux'),
        ('(sun|i86)os', 'solaris'),
        ('iphone', 'iphone'),
        (r'nintendo\s+wii', 'wii'),
        ('irix', 'irix'),
        ('hp-?ux', 'hpux'),
        ('aix', 'aix'),
        ('sco|unix_sv', 'sco'),
        ('bsd', 'bsd'),
        ('amiga', 'amiga')
    )]
    browsers = [(re.compile(r'(?:%s)[/\sa-z(]*(\d+[.\da-z]+)?(?i)' % regex),
                 name) for regex, name in (
        (r'aol|america\s+online\s+browser', 'aol'),
        (r'msie|microsoft\s+internet\s+explorer', 'msie'),
        ('firefox|firebird|phoenix|iceweasel', 'firefox'),
        ('galeon', 'galeon'),
        ('webkit|safari', 'safari'),
        ('opera', 'opera'),
        ('camino', 'camino'),
        ('konqueror', 'konqueror'),
        ('k-meleon', 'k-meleon'),
        ('netscape', 'netscape'),
        (r'playstation\s+portable', 'psp'),
        (r'playstation\s*3', 'ps3'),
        ('lynx', 'lynx')
    )]
    lang = re.compile(
        r'(?:;\s*|\s+)(\b\w{2}\b(?:-\b\w{2}\b)?)\s*;|'
        r'(?:\(|\[|;)\s*(\b\w{2}\b(?:-\b\w{2}\b)?)\s*(?:\]|\)|;)'
    )
    del regex, name

    def __call__(self, user_agent):
        for regex, name in self.platforms:
            if regex.search(user_agent) is not None:
                platform = name
                break
        else:
            platform = None
        for regex, name in self.browsers:
            match = regex.search(user_agent)
            if match is not None:
                browser = name
                version = match.group(1) or None
                break
        else:
            browser = version = None
        match = self.lang.search(user_agent)
        if match is not None:
            language = match.group(1) or match.group(2)
        else:
            language = None
        return {
            'platform':     platform,
            'browser':      browser,
            'version':      version,
            'language':     language
        }


class UserAgent(object):
    """
    Represents a user agent.  Pass it a WSGI environment or an user agent
    string and you can inspect some of the details from the user agent
    string via the attributes.  The following attribute exist:

    -   `platform`, the browser platform
    -   `browser`, the name of the browser
    -   `version`, the version of the browser
    -   `language`, the language of the browser
    """
    _parse = UserAgentParser()

    def __init__(self, environ_or_string):
        if isinstance(environ_or_string, dict):
            environ_or_string = environ_or_string.get('HTTP_USER_AGENT', '')
        self.string = environ_or_string
        self.__dict__.update(self._parse(environ_or_string))

    def to_header(self):
        return self.string

    def __str__(self):
        return self.string

    def __nonzero__(self):
        return bool(self.browser)

    def __repr__(self):
        return '<%s %r/%s>' % (
            self.__class__.__name__,
            self.browser,
            self.version
        )
