# -*- coding: utf-8 -*-
"""
    werkzeug.formparser
    ~~~~~~~~~~~~~~~~~~~

    This module implements the form parsing.  It supports url-encoded forms
    as well as non-nested multipart uploads.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
from cStringIO import StringIO
from tempfile import TemporaryFile
from itertools import chain, repeat

from werkzeug._internal import _decode_unicode, _empty_stream
from werkzeug.urls import url_decode
from werkzeug.wsgi import LimitedStream, make_line_iter
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.datastructures import Headers, FileStorage, MultiDict
from werkzeug.http import parse_options_header


#: an iterator that yields empty strings
_empty_string_iter = repeat('')

#: a regular expression for multipart boundaries
_multipart_boundary_re = re.compile('^[ -~]{0,200}[!-~]$')

#: supported http encodings that are also available in python we support
#: for multipart messages.
_supported_multipart_encodings = frozenset(['base64', 'quoted-printable'])


def default_stream_factory(total_content_length, filename, content_type,
                           content_length=None):
    """The stream factory that is used per default."""
    if total_content_length > 1024 * 500:
        return TemporaryFile('wb+')
    return StringIO()


def parse_form_data(environ, stream_factory=None, charset='utf-8',
                    errors='ignore', max_form_memory_size=None,
                    max_content_length=None, cls=None,
                    silent=True):
    """Parse the form data in the environ and return it as tuple in the form
    ``(stream, form, files)``.  You should only call this method if the
    transport method is `POST` or `PUT`.

    If the mimetype of the data transmitted is `multipart/form-data` the
    files multidict will be filled with `FileStorage` objects.  If the
    mimetype is unknown the input stream is wrapped and returned as first
    argument, else the stream is empty.

    This function does not raise exceptions, even if the input data is
    malformed.

    Have a look at :ref:`dealing-with-request-data` for more details.

    .. versionadded:: 0.5
       The `max_form_memory_size`, `max_content_length` and
       `cls` parameters were added.

    .. versionadded:: 0.5.1
       The optional `silent` flag was added.

    :param environ: the WSGI environment to be used for parsing.
    :param stream_factory: An optional callable that returns a new read and
                           writeable file descriptor.  This callable works
                           the same as :meth:`~BaseResponse._get_file_stream`.
    :param charset: The character set for URL and url encoded form data.
    :param errors: The encoding error behavior.
    :param max_form_memory_size: the maximum number of bytes to be accepted for
                           in-memory stored form data.  If the data
                           exceeds the value specified an
                           :exc:`~exceptions.RequestURITooLarge`
                           exception is raised.
    :param max_content_length: If this is provided and the transmitted data
                               is longer than this value an
                               :exc:`~exceptions.RequestEntityTooLarge`
                               exception is raised.
    :param cls: an optional dict class to use.  If this is not specified
                       or `None` the default :class:`MultiDict` is used.
    :param silent: If set to False parsing errors will not be caught.
    :return: A tuple in the form ``(stream, form, files)``.
    """
    content_type, extra = parse_options_header(environ.get('CONTENT_TYPE', ''))
    try:
        content_length = int(environ['CONTENT_LENGTH'])
    except (KeyError, ValueError):
        content_length = 0

    if cls is None:
        cls = MultiDict

    if max_content_length is not None and content_length > max_content_length:
        raise RequestEntityTooLarge()

    stream = _empty_stream
    files = ()

    if content_type == 'multipart/form-data':
        try:
            form, files = parse_multipart(environ['wsgi.input'],
                                          extra.get('boundary'),
                                          content_length, stream_factory,
                                          charset, errors,
                                          max_form_memory_size=max_form_memory_size)
        except ValueError, e:
            if not silent:
                raise
            form = cls()
        else:
            form = cls(form)
    elif content_type == 'application/x-www-form-urlencoded' or \
         content_type == 'application/x-url-encoded':
        if max_form_memory_size is not None and \
           content_length > max_form_memory_size:
            raise RequestEntityTooLarge()
        form = url_decode(environ['wsgi.input'].read(content_length),
                          charset, errors=errors, cls=cls)
    else:
        form = cls()
        stream = LimitedStream(environ['wsgi.input'], content_length)

    return stream, form, cls(files)


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


def _find_terminator(iterator):
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


def is_valid_multipart_boundary(boundary):
    """Checks if the string given is a valid multipart boundary."""
    return _multipart_boundary_re.match(boundary) is not None


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

    if not boundary:
        raise ValueError('Missing boundary')
    if not is_valid_multipart_boundary(boundary):
        raise ValueError('Invalid boundary: %s' % boundary)
    if len(boundary) > buffer_size: # pragma: no cover
        # this should never happen because we check for a minimum size
        # of 1024 and boundaries may not be longer than 200.  The only
        # situation when this happen is for non debug builds where
        # the assert i skipped.
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
                     _empty_string_iter)

    try:
        terminator = _find_terminator(iterator)
        if terminator != next_part:
            raise ValueError('Expected boundary at start of multipart data')

        while terminator != last_part:
            headers = parse_multipart_headers(iterator)
            disposition = headers.get('content-disposition')
            if disposition is None:
                raise ValueError('Missing Content-Disposition header')
            disposition, extra = parse_options_header(disposition)
            name = extra.get('name')

            transfer_encoding = headers.get('content-transfer-encoding')
            try_decode = transfer_encoding is not None and \
                         transfer_encoding in _supported_multipart_encodings

            filename = extra.get('filename')

            # Figure out input charset for current part
            content_type = headers.get('content-type')
            if content_type:
                mimetype, ct_params = parse_options_header(content_type)
                part_charset = ct_params.get("charset", charset)
            else:
                part_charset = charset

            # if no content type is given we stream into memory.  A list is
            # used as a temporary container.
            if filename is None:
                is_file = False
                container = []
                _write = container.append
                guard_memory = max_form_memory_size is not None

            # otherwise we parse the rest of the headers and ask the stream
            # factory for something we can write in.
            else:
                is_file = True
                guard_memory = False
                if filename is not None:
                    filename = _fix_ie_filename(_decode_unicode(filename,
                                                                charset,
                                                                errors))
                try:
                    content_length = int(headers['content-length'])
                except (KeyError, ValueError):
                    content_length = 0
                container = stream_factory(total_content_length, content_type,
                                           filename, content_length)
                _write = container.write

            buf = ''
            for line in iterator:
                if not line:
                    raise ValueError('unexpected end of stream')

                if line[:2] == '--':
                    terminator = line.rstrip()
                    if terminator in (next_part, last_part):
                        break

                if try_decode:
                    try:
                        line = line.decode(transfer_encoding)
                    except Exception:
                        raise ValueError('could not decode transfer '
                                         'encoded chunk')

                # we have something in the buffer from the last iteration.
                # this is usually a newline delimiter.
                if buf:
                    _write(buf)
                    buf = ''

                # If the line ends with windows CRLF we write everything except
                # the last two bytes.  In all other cases however we write
                # everything except the last byte.  If it was a newline, that's
                # fine, otherwise it does not matter because we will write it
                # the next iteration.  this ensures we do not write the
                # final newline into the stream.  That way we do not have to
                # truncate the stream.  However we do have to make sure that
                # if something else than a newline is in there we write it
                # out.
                if line[-2:] == '\r\n':
                    buf = '\r\n'
                    cutoff = -2
                else:
                    buf = line[-1]
                    cutoff = -1
                _write(line[:cutoff])

                # if we write into memory and there is a memory size limit we
                # count the number of bytes in memory and raise an exception if
                # there is too much data in memory.
                if guard_memory:
                    in_memory += len(line)
                    if in_memory > max_form_memory_size:
                        from werkzeug.exceptions import RequestEntityTooLarge
                        raise RequestEntityTooLarge()
            else: # pragma: no cover
                raise ValueError('unexpected end of part')

            # if we have a leftover in the buffer that is not a newline
            # character we have to flush it, otherwise we will chop of
            # certain values.
            if buf not in ('', '\r', '\n', '\r\n'):
                _write(buf)

            if is_file:
                container.seek(0)
                files.append((name, FileStorage(container, filename, name,
                                                content_type,
                                                content_length, headers)))
            else:
                form.append((name, _decode_unicode(''.join(container),
                                                   part_charset, errors)))
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

    # we link the list to the headers, no need to create a copy, the
    # list was not shared anyways.
    return Headers.linked(result)
