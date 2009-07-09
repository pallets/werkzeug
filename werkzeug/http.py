# -*- coding: utf-8 -*-
"""
    werkzeug.http
    ~~~~~~~~~~~~~

    Werkzeug comes with a bunch of utilties that help Werkzeug to deal with
    HTTP data.  Most of the classes and functions provided by this module are
    used by the wrappers, but they are useful on their own, too, especially if
    the response and request objects are not used.

    This covers some of the more HTTP centric features of WSGI, some other
    utilities such as cookie handling are documented in the `werkzeug.utils`
    module.


    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import inspect
try:
    from email.utils import parsedate_tz, mktime_tz
except ImportError:
    from email.Utils import parsedate_tz, mktime_tz
from cStringIO import StringIO
from tempfile import TemporaryFile
from urllib2 import parse_http_list as _parse_list_header
from datetime import datetime
from itertools import chain, repeat
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
from werkzeug._internal import _decode_unicode, HTTP_STATUS_CODES


_accept_re = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')
_token_chars = frozenset("!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                         '^_`abcdefghijklmnopqrstuvwxyz|~')
_etag_re = re.compile(r'([Ww]/)?(?:"(.*?)"|(.*?))(?:\s*,\s*|$)')
_multipart_boundary_re = re.compile('^[ -~]{0,200}[!-~]$')

_entity_headers = frozenset([
    'allow', 'content-encoding', 'content-language', 'content-length',
    'content-location', 'content-md5', 'content-range', 'content-type',
    'expires', 'last-modified'
])
_hop_by_pop_headers = frozenset([
    'connection', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
    'upgrade'
])

#: supported http encodings that are also available in python we support
#: for multipart messages.
_supported_multipart_encodings = frozenset(['base64', 'quoted-printable'])


def quote_header_value(value, extra_chars='', allow_token=True):
    """Quote a header value if necessary.

    .. versionadded:: 0.5

    :param value: the value to quote.
    :param extra_chars: a list of extra characters to skip quoting.
    :param allow_token: if this is enabled token values are returned
                        unchanged.
    """
    value = str(value)
    if allow_token:
        token_chars = _token_chars | set(extra_chars)
        if set(value).issubset(token_chars):
            return value
    return '"%s"' % value.replace('\\', '\\\\').replace('"', '\\"')


def unquote_header_value(value):
    r"""Unquotes a header value.  (Reversal of :func:`quote_header_value`).
    This does not use the real unquoting but what browsers are actually
    using for quoting.

    .. versionadded:: 0.5

    :param value: the header value to unquote.
    """
    if value and value[0] == value[-1] == '"':
        # this is not the real unquoting, but fixing this so that the
        # RFC is met will result in bugs with internet explorer and
        # probably some other browsers as well.  IE for example is
        # uploading files with "C:\foo\bar.txt" as filename
        value = value[1:-1].replace('\\\\', '\\').replace('\\"', '"')
    return value


def dump_options_header(header, options):
    """The reverse function to :func:`parse_options_header`.

    :param header: the header to dump
    :param options: a dict of options to append.
    """
    segments = []
    if header is not None:
        segments.append(header)
    for key, value in options.iteritems():
        if value is None:
            segments.append(key)
        else:
            segments.append('%s=%s' % (key, quote_header_value(value)))
    return '; '.join(segments)


def dump_header(iterable, allow_token=True):
    """Dump an HTTP header again.  This is the reversal of
    :func:`parse_list_header`, :func:`parse_set_header` and
    :func:`parse_dict_header`.  This also quotes strings that include an
    equals sign unless you pass it as dict of key, value pairs.

    :param iterable: the iterable or dict of values to quote.
    :param allow_token: if set to `False` tokens as values are disallowed.
                        See :func:`quote_header_value` for more details.
    """
    if isinstance(iterable, dict):
        items = []
        for key, value in iterable.iteritems():
            if value is None:
                items.append(key)
            else:
                items.append('%s=%s' % (
                    key,
                    quote_header_value(value, allow_token=allow_token)
                ))
    else:
        items = [quote_header_value(x, allow_token=allow_token)
                 for x in iterable]
    return ', '.join(items)


def parse_list_header(value):
    """Parse lists as described by RFC 2068 Section 2.

    In particular, parse comma-separated lists where the elements of
    the list may include quoted-strings.  A quoted-string could
    contain a comma.  A non-quoted string could have quotes in the
    middle.  Quotes are removed automatically after parsing.

    :param value: a string with a list header.
    :return: list
    """
    result = []
    for item in _parse_list_header(value):
        if item[:1] == item[-1:] == '"':
            item = unquote_header_value(item[1:-1])
        result.append(item)
    return result


def parse_dict_header(value):
    """Parse lists of key, value pairs as described by RFC 2068 Section 2 and
    convert them into a python dict.  If there is no value for a key it will
    be `None`.

    :param value: a string with a dict header.
    :return: dict
    """
    result = {}
    for item in _parse_list_header(value):
        if '=' not in item:
            result[item] = None
            continue
        name, value = item.split('=', 1)
        if value[:1] == value[-1:] == '"':
            value = unquote_header_value(value[1:-1])
        result[name] = value
    return result


def parse_options_header(value):
    """Parse a ``Content-Type`` like header into a tuple with the content
    type and the options:

    >>> parse_options_header('Content-Type: text/html; mimetype=text/html')
    ('Content-Type: text/html', {'mimetype': 'text/html'})

    This should not be used to parse ``Cache-Control`` like headers that use
    a slightly different format.  For these headers use the
    :func:`parse_dict_header` function.

    .. versionadded:: 0.5

    :param value: the header to parse.
    :return: (str, options)
    """
    def _tokenize(string):
        while string[:1] == ';':
            string = string[1:]
            end = string.find(';')
            while end > 0 and string.count('"', 0, end) % 2:
                end = string.find(';', end + 1)
            if end < 0:
                end = len(string)
            value = string[:end]
            yield value.strip()
            string = string[end:]

    parts = _tokenize(';' + value)
    name = parts.next()
    extra = {}
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            extra[key.strip().lower()] = unquote_header_value(value.strip())
        else:
            extra[part.strip()] = None
    return name, extra


def parse_accept_header(value, cls=None):
    """Parses an HTTP Accept-* header.  This does not implement a complete
    valid algorithm but one that supports at least value and quality
    extraction.

    Returns a new :class:`Accept` object (basically a list of ``(value, quality)``
    tuples sorted by the quality with some additional accessor methods).

    The second parameter can be a subclass of :class:`Accept` that is created
    with the parsed values and returned.

    :param value: the accept header string to be parsed.
    :param cls: the wrapper class for the return value (can be
                         :class:`Accept` or a subclass thereof)
    :return: an instance of `cls`.
    """
    if cls is None:
        cls = Accept

    if not value:
        return cls(None)

    result = []
    for match in _accept_re.finditer(value):
        quality = match.group(2)
        if not quality:
            quality = 1
        else:
            quality = max(min(float(quality), 1), 0)
        result.append((match.group(1), quality))
    return cls(result)


def parse_cache_control_header(value, on_update=None, cls=None):
    """Parse a cache control header.  The RFC differs between response and
    request cache control, this method does not.  It's your responsibility
    to not use the wrong control statements.

    .. versionadded:: 0.5
       The `cls` was added.  If not specified an immutable
       :class:`RequestCacheControl` is returned.

    :param value: a cache control header to be parsed.
    :param on_update: an optional callable that is called every time a
                      value on the :class:`CacheControl` object is changed.
    :param cls: the class for the returned object.  By default
                                :class:`RequestCacheControl` is used.
    :return: a `cls` object.
    """
    if cls is None:
        cls = RequestCacheControl
    if not value:
        return cls(None, on_update)
    return cls(parse_dict_header(value), on_update)


def parse_set_header(value, on_update=None):
    """Parse a set-like header and return a :class:`HeaderSet` object.  The
    return value is an object that treats the items case-insensitively and
    keeps the order of the items.

    :param value: a set header to be parsed.
    :param on_update: an optional callable that is called every time a
                      value on the :class:`HeaderSet` object is changed.
    :return: a :class:`HeaderSet`
    """
    if not value:
        return HeaderSet(None, on_update)
    return HeaderSet(parse_list_header(value), on_update)


def parse_authorization_header(value):
    """Parse an HTTP basic/digest authorization header transmitted by the web
    browser.  The return value is either `None` if the header was invalid or
    not given, otherwise an :class:`Authorization` object.

    :param value: the authorization header to parse.
    :return: a :class:`Authorization` object or `None`.
    """
    if not value:
        return
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except ValueError:
        return
    if auth_type == 'basic':
        try:
            username, password = auth_info.decode('base64').split(':', 1)
        except Exception, e:
            return
        return Authorization('basic', {'username': username,
                                       'password': password})
    elif auth_type == 'digest':
        auth_map = parse_dict_header(auth_info)
        for key in 'username', 'realm', 'nonce', 'uri', 'nc', 'cnonce', \
                   'response':
            if not key in auth_map:
                return
        return Authorization('digest', auth_map)


def parse_www_authenticate_header(value, on_update=None):
    """Parse an HTTP WWW-Authenticate header into a :class:`WWWAuthenticate`
    object.

    :param value: a WWW-Authenticate header to parse.
    :param on_update: an optional callable that is called every time a
                      value on the :class:`WWWAuthenticate` object is changed.
    :return: a :class:`WWWAuthenticate` object.
    """
    if not value:
        return WWWAuthenticate(on_update=on_update)
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except (ValueError, AttributeError):
        return WWWAuthenticate(value.lower(), on_update=on_update)
    return WWWAuthenticate(auth_type, parse_dict_header(auth_info),
                           on_update)


def quote_etag(etag, weak=False):
    """Quote an etag.

    :param etag: the etag to quote.
    :param weak: set to `True` to tag it "weak".
    """
    if '"' in etag:
        raise ValueError('invalid etag')
    etag = '"%s"' % etag
    if weak:
        etag = 'w/' + etag
    return etag


def unquote_etag(etag):
    """Unquote a single etag:

    >>> unquote_etag('w/"bar"')
    ('bar', True)
    >>> unquote_etag('"bar"')
    ('bar', False)

    :param etag: the etag identifier to unquote.
    :return: a ``(etag, weak)`` tuple.
    """
    if not etag:
        return None, None
    etag = etag.strip()
    weak = False
    if etag[:2] in ('w/', 'W/'):
        weak = True
        etag = etag[2:]
    if etag[:1] == etag[-1:] == '"':
        etag = etag[1:-1]
    return etag, weak


def parse_etags(value):
    """Parse an etag header.

    :param value: the tag header to parse
    :return: an :class:`ETags` object.
    """
    if not value:
        return ETags()
    strong = []
    weak = []
    end = len(value)
    pos = 0
    while pos < end:
        match = _etag_re.match(value, pos)
        if match is None:
            break
        is_weak, quoted, raw = match.groups()
        if raw == '*':
            return ETags(star_tag=True)
        elif quoted:
            raw = quoted
        if is_weak:
            weak.append(raw)
        else:
            strong.append(raw)
        pos = match.end()
    return ETags(strong, weak)


def generate_etag(data):
    """Generate an etag for some data."""
    return md5(data).hexdigest()


def parse_date(value):
    """Parse one of the following date formats into a datetime object:

    .. sourcecode:: text

        Sun, 06 Nov 1994 08:49:37 GMT  ; RFC 822, updated by RFC 1123
        Sunday, 06-Nov-94 08:49:37 GMT ; RFC 850, obsoleted by RFC 1036
        Sun Nov  6 08:49:37 1994       ; ANSI C's asctime() format

    If parsing fails the return value is `None`.

    :param value: a string with a supported date format.
    :return: a :class:`datetime.datetime` object.
    """
    if value:
        t = parsedate_tz(value.strip())
        if t is not None:
            # if no timezone is part of the string we assume UTC
            if t[-1] is None:
                t = t[:-1] + (0,)
            return datetime.utcfromtimestamp(mktime_tz(t))


def default_stream_factory(total_content_length, filename, content_type,
                           content_length=None):
    """The stream factory that is used per default."""
    if total_content_length > 1024 * 500:
        return TemporaryFile('wb+')
    return StringIO()


def _make_stream_factory(factory):
    """this exists for backwards compatibility!, will go away in 0.6."""
    args, _, _, defaults = inspect.getargspec(factory)
    required_args = len(args) - len(defaults or ())
    if inspect.ismethod(factory):
        required_args -= 1
    if required_args != 0:
        return factory
    from warnings import warn
    warn(DeprecationWarning('stream factory passed to `parse_form_data` '
                            'uses deprecated invokation API.'), stacklevel=4)
    return lambda *a: factory()


def _fix_ie_filename(filename):
    """Internet Explorer 6 transmits the full file name if a file is
    uploaded.  This function strips the full path if it thinks the
    filename is Windows-like absolute.
    """
    if filename[1:3] == ':\\' or filename[:2] == '\\\\':
        return filename.split('\\')[-1]
    return filename


def _line_parse(line):
    """Removes line ending characters and returns a tuple (`stripped_line`,
    `is_terminated`).
    """
    if line[-2:] == '\r\n':
        return line[:-2], True
    elif line[-1:] in '\r\n':
        return line[:-1], True
    return line, False


def parse_multipart(file, boundary, content_length, stream_factory=None,
                    charset='utf-8', errors='ignore', buffer_size=10 * 1024,
                    max_form_memory_size=None):
    """Parse a multipart/form-data stream.  This is invoked by
    :func:`utils.parse_form_data` if the content type matches.  Currently it
    exists for internal usage only, but could be exposed as separate
    function if it turns out to be useful and if we consider the API stable.
    """
    # XXX: this function does not support multipart/mixed.  I don't know of
    #      any browser that supports this, but it should be implemented
    #      nonetheless.

    # make sure the buffer size is divisible by four so that we can base64
    # decode chunk by chunk
    assert buffer_size % 4 == 0, 'buffer size has to be divisible by 4'
    # also the buffer size has to be at least 1024 bytes long or long headers
    # will freak out the system
    assert buffer_size >= 1024, 'buffer size has to be at least 1KB'

    if stream_factory is None:
        stream_factory = default_stream_factory
    else:
        stream_factory = _make_stream_factory(stream_factory)

    if not boundary:
        raise ValueError('Missing boundary')
    if not is_valid_multipart_boundary(boundary):
        raise ValueError('Invalid boundary: %s' % boundary)
    if len(boundary) > buffer_size:
        raise ValueError('Boundary longer than buffer size')

    total_content_length = content_length
    next_part = '--' + boundary
    last_part = next_part + '--'

    form = []
    files = []
    in_memory = 0

    # convert the file into a limited stream with iteration capabilities
    file = LimitedStream(file, content_length)
    iterator = chain(make_line_iter(file, buffer_size=buffer_size),
                     repeat(''))

    def _find_terminator():
        """The terminator might have some additional newlines before it.
        There is at least one application that sends additional newlines
        before headers (the python setuptools package).
        """
        for line in iterator:
            if not line:
                break
            line = line.strip()
            if line:
                return line
        return ''

    try:
        terminator = _find_terminator()
        if terminator != next_part:
            raise ValueError('Expected boundary at start of multipart data')

        while terminator != last_part:
            headers = parse_multipart_headers(iterator)
            disposition = headers.get('content-disposition')
            if disposition is None:
                raise ValueError('Missing Content-Disposition header')
            disposition, extra = parse_options_header(disposition)
            filename = extra.get('filename')
            name = extra.get('name')
            transfer_encoding = headers.get('content-transfer-encoding')

            content_type = headers.get('content-type')
            if content_type is None:
                is_file = False
            else:
                content_type = parse_options_header(content_type)[0]
                is_file = True

            if is_file:
                if filename is not None:
                    filename = _fix_ie_filename(_decode_unicode(filename,
                                                                charset,
                                                                errors))
                try:
                    content_length = int(headers['content-length'])
                except (KeyError, ValueError):
                    content_length = 0
                stream = stream_factory(total_content_length, content_type,
                                        filename, content_length)
            else:
                stream = StringIO()

            buf = ''
            for line in iterator:
                if not line:
                    raise ValueError('unexpected end of stream')
                if line[:2] == '--':
                    terminator = line.rstrip()
                    if terminator in (next_part, last_part):
                        break
                if transfer_encoding in _supported_multipart_encodings:
                    try:
                        line = line.decode(transfer_encoding)
                    except:
                        raise ValueError('could not base 64 decode chunk')
                # we have something in the buffer from the last iteration.
                # write that value to the output stream now and clear the buffer.
                if buf:
                    stream.write(buf)
                    buf = ''

                # If the line ends with windows CRLF we write everything except
                # the last two bytes.  In all other cases however we write everything
                # except the last byte.  If it was a newline, that's fine, otherwise
                # it does not matter because we write it the last iteration.  If the
                # loop aborts early because the end of a part was reached, the last
                # newline is not written which is exactly what we want.
                newline_length = line[-2:] == '\r\n' and 2 or 1
                stream.write(line[:-newline_length])
                buf = line[-newline_length:]
                if not is_file and max_form_memory_size is not None:
                    in_memory += len(line)
                    if in_memory > max_form_memory_size:
                        from werkzeug.exceptions import RequestEntityTooLarge
                        raise RequestEntityTooLarge()
            else:
                raise ValueError('unexpected end of part')

            # rewind the stream
            stream.seek(0)

            if is_file:
                files.append((name, FileStorage(stream, filename, name,
                                                content_type,
                                                content_length)))
            else:
                form.append((name, _decode_unicode(stream.read(),
                                                   charset, errors)))
    finally:
        # make sure the whole input stream is read
        file.exhaust()

    return form, files


def parse_multipart_headers(iterable):
    """Parses multipart headers from an iterable that yields lines (including
    the trailing newline symbol.
    """
    result = []
    for line in iterable:
        line, line_terminated = _line_parse(line)
        if not line_terminated:
            raise ValueError('unexpected end of line in multipart header')
        if not line:
            break
        elif line[0] in ' \t' and result:
            key, value = result[-1]
            result[-1] = (key, value + '\n ' + line[1:])
        else:
            parts = line.split(':', 1)
            if len(parts) == 2:
                result.append((parts[0].strip(), parts[1].strip()))
    return Headers(result)


def is_resource_modified(environ, etag=None, data=None, last_modified=None):
    """Convenience method for conditional requests.

    :param environ: the WSGI environment of the request to be checked.
    :param etag: the etag for the response for comparision.
    :param data: or alternatively the data of the response to automatically
                 generate an etag using :func:`generate_etag`.
    :param last_modified: an optional date of the last modification.
    :return: `True` if the resource was modified, otherwise `False`.
    """
    if etag is None and data is not None:
        etag = generate_etag(data)
    elif data is not None:
        raise TypeError('both data and etag given')
    if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
        return False

    unmodified = False
    if isinstance(last_modified, basestring):
        last_modified = parse_date(last_modified)
    modified_since = parse_date(environ.get('HTTP_IF_MODIFIED_SINCE'))

    if modified_since and last_modified and last_modified <= modified_since:
        unmodified = True
    if etag:
        if_none_match = parse_etags(environ.get('HTTP_IF_NONE_MATCH'))
        if if_none_match:
            unmodified = if_none_match.contains_raw(etag)

    return not unmodified


def remove_entity_headers(headers, allowed=('expires', 'content-location')):
    """Remove all entity headers from a list or :class:`Headers` object.  This
    operation works in-place.  `Expires` and `Content-Location` headers are
    by default not removed.  The reason for this is :rfc:`2616` section
    10.3.5 which specifies some entity headers that should be sent.

    .. versionchanged:: 0.5
       added `allowed` parameter.

    :param headers: a list or :class:`Headers` object.
    :param allowed: a list of headers that should still be allowed even though
                    they are entity headers.
    """
    allowed = set(x.lower() for x in allowed)
    headers[:] = [(key, value) for key, value in headers if
                  not is_entity_header(key) or key.lower() in allowed]


def remove_hop_by_hop_headers(headers):
    """Remove all HTTP/1.1 "Hop-by-Hop" headers from a list or
    :class:`Headers` object.  This operation works in-place.

    .. versionadded:: 0.5

    :param headers: a list or :class:`Headers` object.
    """
    headers[:] = [(key, value) for key, value in headers if
                  not is_hop_by_hop_header(key)]


def is_entity_header(header):
    """Check if a header is an entity header.

    .. versionadded:: 0.5

    :param header: the header to test.
    :return: `True` if it's an entity header, `False` otherwise.
    """
    return header.lower() in _entity_headers


def is_hop_by_hop_header(header):
    """Check if a header is an HTTP/1.1 "Hop-by-Hop" header.

    .. versionadded:: 0.5

    :param header: the header to test.
    :return: `True` if it's an entity header, `False` otherwise.
    """
    return header.lower() in _hop_by_pop_headers


def is_valid_multipart_boundary(boundary):
    """Checks if the string given is a valid multipart boundary."""
    return _multipart_boundary_re.match(boundary) is not None


# circular dependency fun
from werkzeug.utils import make_line_iter, FileStorage, LimitedStream
from werkzeug.datastructures import Headers, Accept, RequestCacheControl, \
     ResponseCacheControl, HeaderSet, ETags, Authorization, \
     WWWAuthenticate


# DEPRECATED
# backwards compatibible imports
from werkzeug.datastructures import MIMEAccept, CharsetAccept, LanguageAccept
