# -*- coding: utf-8 -*-
"""
    werkzeug.formparser
    ~~~~~~~~~~~~~~~~~~~

    This module implements the form parsing.  It supports url-encoded forms
    as well as non-nested multipart uploads.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import codecs
import re
from functools import update_wrapper
from itertools import repeat
from itertools import tee

from ._compat import BytesIO
from ._compat import text_type
from ._compat import to_native
from .datastructures import FileStorage
from .datastructures import Headers
from .datastructures import MultiDict
from .http import parse_options_header
from .urls import url_decode_stream
from .wsgi import get_content_length
from .wsgi import get_input_stream

# there are some platforms where SpooledTemporaryFile is not available.
# In that case we need to provide a fallback.
try:
    from tempfile import SpooledTemporaryFile
except ImportError:
    from tempfile import TemporaryFile

    SpooledTemporaryFile = None


#: an iterator that yields empty strings
_empty_string_iter = repeat("")

#: a regular expression for multipart boundaries
_multipart_boundary_re = re.compile("^[ -~]{0,200}[!-~]$")

#: supported http encodings that are also available in python we support
#: for multipart messages.
_supported_multipart_encodings = frozenset(["base64", "quoted-printable"])


def default_stream_factory(
    total_content_length, filename, content_type, content_length=None
):
    """The stream factory that is used per default."""
    max_size = 1024 * 500
    if SpooledTemporaryFile is not None:
        return SpooledTemporaryFile(max_size=max_size, mode="wb+")
    if total_content_length is None or total_content_length > max_size:
        return TemporaryFile("wb+")
    return BytesIO()


def parse_form_data(
    environ,
    stream_factory=None,
    charset="utf-8",
    errors="replace",
    max_form_memory_size=None,
    max_content_length=None,
    cls=None,
    silent=True,
):
    """Parse the form data in the environ and return it as tuple in the form
    ``(stream, form, files)``.  You should only call this method if the
    transport method is `POST`, `PUT`, or `PATCH`.

    If the mimetype of the data transmitted is `multipart/form-data` the
    files multidict will be filled with `FileStorage` objects.  If the
    mimetype is unknown the input stream is wrapped and returned as first
    argument, else the stream is empty.

    This is a shortcut for the common usage of :class:`FormDataParser`.

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
                           :exc:`~exceptions.RequestEntityTooLarge`
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
    return FormDataParser(
        stream_factory,
        charset,
        errors,
        max_form_memory_size,
        max_content_length,
        cls,
        silent,
    ).parse_from_environ(environ)


def exhaust_stream(f):
    """Helper decorator for methods that exhausts the stream on return."""

    def wrapper(self, stream, *args, **kwargs):
        try:
            return f(self, stream, *args, **kwargs)
        finally:
            exhaust = getattr(stream, "exhaust", None)
            if exhaust is not None:
                exhaust()
            else:
                while 1:
                    chunk = stream.read(1024 * 64)
                    if not chunk:
                        break

    return update_wrapper(wrapper, f)


class FormDataParser(object):
    """This class implements parsing of form data for Werkzeug.  By itself
    it can parse multipart and url encoded form data.  It can be subclassed
    and extended but for most mimetypes it is a better idea to use the
    untouched stream and expose it as separate attributes on a request
    object.

    .. versionadded:: 0.8

    :param stream_factory: An optional callable that returns a new read and
                           writeable file descriptor.  This callable works
                           the same as :meth:`~BaseResponse._get_file_stream`.
    :param charset: The character set for URL and url encoded form data.
    :param errors: The encoding error behavior.
    :param max_form_memory_size: the maximum number of bytes to be accepted for
                           in-memory stored form data.  If the data
                           exceeds the value specified an
                           :exc:`~exceptions.RequestEntityTooLarge`
                           exception is raised.
    :param max_content_length: If this is provided and the transmitted data
                               is longer than this value an
                               :exc:`~exceptions.RequestEntityTooLarge`
                               exception is raised.
    :param cls: an optional dict class to use.  If this is not specified
                       or `None` the default :class:`MultiDict` is used.
    :param silent: If set to False parsing errors will not be caught.
    """

    def __init__(
        self,
        stream_factory=None,
        charset="utf-8",
        errors="replace",
        max_form_memory_size=None,
        max_content_length=None,
        cls=None,
        silent=True,
    ):
        if stream_factory is None:
            stream_factory = default_stream_factory
        self.stream_factory = stream_factory
        self.charset = charset
        self.errors = errors
        self.max_form_memory_size = max_form_memory_size
        self.max_content_length = max_content_length
        if cls is None:
            cls = MultiDict
        self.cls = cls
        self.silent = silent

    def get_parse_func(self, mimetype, options):
        return self.parse_functions.get(mimetype)

    def parse_from_environ(self, environ):
        """Parses the information from the environment as form data.

        :param environ: the WSGI environment to be used for parsing.
        :return: A tuple in the form ``(stream, form, files)``.
        """
        content_type = environ.get("CONTENT_TYPE", "")
        content_length = get_content_length(environ)
        mimetype, options = parse_options_header(content_type)
        return self.parse(get_input_stream(environ), mimetype, content_length, options)

    def parse(self, stream, mimetype, content_length, options=None):
        """Parses the information from the given stream, mimetype,
        content length and mimetype parameters.

        :param stream: an input stream
        :param mimetype: the mimetype of the data
        :param content_length: the content length of the incoming data
        :param options: optional mimetype parameters (used for
                        the multipart boundary for instance)
        :return: A tuple in the form ``(stream, form, files)``.
        """
        if (
            self.max_content_length is not None
            and content_length is not None
            and content_length > self.max_content_length
        ):
            raise exceptions.RequestEntityTooLarge()
        if options is None:
            options = {}

        parse_func = self.get_parse_func(mimetype, options)
        if parse_func is not None:
            try:
                return parse_func(self, stream, mimetype, content_length, options)
            except ValueError:
                if not self.silent:
                    raise

        return stream, self.cls(), self.cls()

    @exhaust_stream
    def _parse_multipart(self, stream, mimetype, content_length, options):
        parser = MultiPartParser(
            self.stream_factory,
            self.charset,
            self.errors,
            max_form_memory_size=self.max_form_memory_size,
            cls=self.cls,
        )
        boundary = options.get("boundary")
        if boundary is None:
            raise ValueError("Missing boundary")
        if isinstance(boundary, text_type):
            boundary = boundary.encode("ascii")
        form, files = parser.parse(stream, boundary, content_length)
        return stream, form, files

    @exhaust_stream
    def _parse_urlencoded(self, stream, mimetype, content_length, options):
        if (
            self.max_form_memory_size is not None
            and content_length is not None
            and content_length > self.max_form_memory_size
        ):
            raise exceptions.RequestEntityTooLarge()
        form = url_decode_stream(stream, self.charset, errors=self.errors, cls=self.cls)
        return stream, form, self.cls()

    #: mapping of mimetypes to parsing functions
    parse_functions = {
        "multipart/form-data": _parse_multipart,
        "application/x-www-form-urlencoded": _parse_urlencoded,
        "application/x-url-encoded": _parse_urlencoded,
    }


def is_valid_multipart_boundary(boundary):
    """Checks if the string given is a valid multipart boundary."""
    return _multipart_boundary_re.match(boundary) is not None


def _line_parse(line):
    """Removes line ending characters and returns a tuple (`stripped_line`,
    `is_terminated`).
    """
    if line[-2:] in ["\r\n", b"\r\n"]:
        return line[:-2], True
    elif line[-1:] in ["\r", "\n", b"\r", b"\n"]:
        return line[:-1], True
    return line, False


def parse_multipart_headers(iterable):
    """Parses multipart headers from an iterable that yields lines (including
    the trailing newline symbol).  The iterable has to be newline terminated.

    The iterable will stop at the line where the headers ended so it can be
    further consumed.

    :param iterable: iterable of strings that are newline terminated
    """
    result = []
    for line in iterable:
        line = to_native(line)
        line, line_terminated = _line_parse(line)
        if not line_terminated:
            raise ValueError("unexpected end of line in multipart header")
        if not line:
            break
        elif line[0] in " \t" and result:
            key, value = result[-1]
            result[-1] = (key, value + "\n " + line[1:])
        else:
            parts = line.split(":", 1)
            if len(parts) == 2:
                result.append((parts[0].strip(), parts[1].strip()))

    # we link the list to the headers, no need to create a copy, the
    # list was not shared anyways.
    return Headers(result)


_begin_form = "begin_form"
_begin_file = "begin_file"
_cont = "cont"
_end = "end"


class MultiPartParser(object):
    def __init__(
        self,
        stream_factory=None,
        charset="utf-8",
        errors="replace",
        max_form_memory_size=None,
        cls=None,
        buffer_size=64 * 1024,
    ):
        self.charset = charset
        self.errors = errors
        self.max_form_memory_size = max_form_memory_size
        self.stream_factory = (
            default_stream_factory if stream_factory is None else stream_factory
        )
        self.cls = MultiDict if cls is None else cls

        # make sure the buffer size is divisible by four so that we can base64
        # decode chunk by chunk
        assert buffer_size % 4 == 0, "buffer size has to be divisible by 4"
        # also the buffer size has to be at least 1024 bytes long or long headers
        # will freak out the system
        assert buffer_size >= 1024, "buffer size has to be at least 1KB"

        self.buffer_size = buffer_size

    def _fix_ie_filename(self, filename):
        """Internet Explorer 6 transmits the full file name if a file is
        uploaded.  This function strips the full path if it thinks the
        filename is Windows-like absolute.
        """
        if filename[1:3] == ":\\" or filename[:2] == "\\\\":
            return filename.split("\\")[-1]
        return filename

    def _find_terminator(self, iterator):
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
        return b""

    def fail(self, message):
        raise ValueError(message)

    def get_part_encoding(self, headers):
        transfer_encoding = headers.get("content-transfer-encoding")
        if (
            transfer_encoding is not None
            and transfer_encoding in _supported_multipart_encodings
        ):
            return transfer_encoding

    def get_part_charset(self, headers):
        # Figure out input charset for current part
        content_type = headers.get("content-type")
        if content_type:
            mimetype, ct_params = parse_options_header(content_type)
            return ct_params.get("charset", self.charset)
        return self.charset

    def start_file_streaming(self, filename, headers, total_content_length):
        if isinstance(filename, bytes):
            filename = filename.decode(self.charset, self.errors)
        filename = self._fix_ie_filename(filename)
        content_type = headers.get("content-type")
        try:
            content_length = int(headers["content-length"])
        except (KeyError, ValueError):
            content_length = 0
        container = self.stream_factory(
            total_content_length=total_content_length,
            filename=filename,
            content_type=content_type,
            content_length=content_length,
        )
        return filename, container

    def in_memory_threshold_reached(self, bytes):
        raise exceptions.RequestEntityTooLarge()

    def validate_boundary(self, boundary):
        if not boundary:
            self.fail("Missing boundary")
        if not is_valid_multipart_boundary(boundary):
            self.fail("Invalid boundary: %s" % boundary)
        if len(boundary) > self.buffer_size:  # pragma: no cover
            # this should never happen because we check for a minimum size
            # of 1024 and boundaries may not be longer than 200.  The only
            # situation when this happens is for non debug builds where
            # the assert is skipped.
            self.fail("Boundary longer than buffer size")

    class LineSplitter(object):

        """A stateful line splitter: call ``feed`` to push data in and receive
        it split into lines.

        :param cap: Optional maximum length of a line; if this is given,
                    lines will be truncated to meet it.

        ..versionadded:: 0.15
        """

        def __init__(self, cap=None):
            self.buffer = b""
            self.cap = cap

        def _splitlines(self, pre, post):
            # for most purposes, there is no difference between what we've
            # just accepted and any other data. we accept them separately
            # so we can tell if we're ending; see below.
            buf = pre + post
            rv = []
            if not buf:
                return rv, b""
            lines = buf.splitlines(True)
            iv = b""
            for line in lines:
                iv += line
                while self.cap and len(iv) >= self.cap:
                    rv.append(iv[: self.cap])
                    iv = iv[self.cap :]
                if line[-1:] in b"\r\n":
                    rv.append(iv)
                    iv = b""
            # If this isn't the very end of the stream and what we got ends
            # with \r, we need to hold on to it in case an \n comes next
            if post and rv and not iv and rv[-1][-1:] == b"\r":
                iv = rv[-1]
                del rv[-1]
            return rv, iv

        def feed(self, data):
            """Accepts a block of data to be split into lines, returning a list
            of complete lines, including their terminator characters.

            Feeding an empty block of data will end the parse, returning
            an unterminated line, if any, and an empty string."""
            lines, self.buffer = self._splitlines(self.buffer, data)
            if not data:
                lines += [self.buffer]
                if self.buffer:
                    lines += [b""]
            return lines

    class LineParser(object):

        """Parses lines as form data, generating the same output as
        ``parse_lines``, but as a state machine."""

        def __init__(self, parent, boundary):
            self.parent = parent
            self.boundary = boundary
            self._next_part = b"--" + boundary
            self._last_part = self._next_part + b"--"
            self._state = self._state_pre_term
            self._output = []
            self._headers = []
            self._tail = b""
            self._codec = None

        def _start_content(self):
            disposition = self._headers.get("content-disposition")
            if disposition is None:
                raise ValueError("Missing Content-Disposition header")
            self.disposition, extra = parse_options_header(disposition)
            transfer_encoding = self.parent.get_part_encoding(self._headers)
            if transfer_encoding is not None:
                if transfer_encoding == "base64":
                    transfer_encoding = "base64_codec"
                try:
                    self._codec = codecs.lookup(transfer_encoding)
                except Exception:
                    raise ValueError(
                        "Cannot decode transfer-encoding: %r" % transfer_encoding
                    )
            self.name = extra.get("name")
            self.filename = extra.get("filename")
            if self.filename is not None:
                self._output.append(
                    ("begin_file", (self._headers, self.name, self.filename))
                )
            else:
                self._output.append(("begin_form", (self._headers, self.name)))
            return self._state_output

        def _state_done(self, line):
            return self._state_done

        def _state_output(self, line):
            """State for the body of a field; generate pieces of it."""
            if not line:
                raise ValueError("Unexpected end of file")
            sline = line.rstrip()
            if sline == self._last_part:
                self._tail = b""
                self._output.append(("end", None))
                return self._state_done
            elif sline == self._next_part:
                self._tail = b""
                self._output.append(("end", None))
                self._headers = []
                return self._state_headers

            if self._codec:
                try:
                    line, _ = self._codec.decode(line)
                except Exception:
                    raise ValueError("Could not decode transfer-encoded chunk")

            # We don't know yet whether we can output the final newline, so
            # we'll save it in self._tail and output it next time.
            tail = self._tail
            if line[-2:] == b"\r\n":
                self._output.append(("cont", tail + line[:-2]))
                self._tail = line[-2:]
            elif line[-1:] in b"\r\n":
                self._output.append(("cont", tail + line[:-1]))
                self._tail = line[-1:]
            else:
                self._output.append(("cont", tail + line))
                self._tail = b""
            return self._state_output

        def _state_pre_term(self, line):
            """State for the very beginning of the stream, before any content.
            Eats empty lines until it finds a boundary line."""
            if not line:
                raise ValueError("Unexpected end of file")
                return self._state_pre_term
            line = line.rstrip(b"\r\n")
            if not line:
                return self._state_pre_term
            if line == self._last_part:
                return self._state_done
            elif line == self._next_part:
                self._headers = []
                return self._state_headers
            raise ValueError("Expected boundary at start of multipart data")

        def _state_headers(self, line):
            """State for field headers. They are parsed and left in
            ``self._headers``."""
            if line is None:
                raise ValueError("Unexpected end of file during headers")
            line = to_native(line)
            line, line_terminated = _line_parse(line)
            if not line_terminated:
                raise ValueError("Unexpected end of line in multipart header")
            if not line:
                self._headers = Headers(self._headers)
                return self._start_content()
            if line[0] in " \t" and self._headers:
                key, value = self._headers[-1]
                self._headers[-1] = (key, value + "\n " + line[1:])
            else:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    self._headers.append((parts[0].strip(), parts[1].strip()))
                else:
                    raise ValueError("Malformed header")
            return self._state_headers

        def feed(self, lines):
            self._output = []
            s = self._state
            for line in lines:
                s = s(line)
            self._state = s
            return self._output

    class PartParser(object):
        def __init__(self, parent):
            self.parent = parent
            self._write = None
            self._in_memory = 0
            self._guard_memory = parent.max_form_memory_size is not None

        def _feed_one(self, event):
            ev, data = event
            p = self.parent
            if ev == "begin_file":
                self._is_file = True
            elif ev == "begin_form":
                self._headers, self._name = data
                self._container = []
                self._write = self._container.append
                self._is_file = False

            if self._is_file:
                return event

            if ev == "cont":
                self._write(data)
                if self._guard_memory:
                    self._in_memory += len(data)
                    if self._in_memory > p.max_form_memory_size:
                        p.in_memory_threshold_reached(self._in_memory)
            elif ev == "end":
                part_charset = p.get_part_charset(self._headers)
                return (
                    "form",
                    (
                        self._name,
                        b"".join(self._container).decode(part_charset, p.errors),
                    ),
                )

        def feed(self, events):
            rv = []
            for event in events:
                v = self._feed_one(event)
                if v is not None:
                    rv.append(v)
            return rv

    class FileWriter(object):
        def __init__(self, parent, content_length):
            self.parent = parent
            self.content_length = content_length
            self._file = None

        def _feed_one(self, event):
            ev, data = event
            if ev == "begin_file":
                self._headers, self._name, filename = data
                self._filename, self._file = self.parent.start_file_streaming(
                    filename, self._headers, self.content_length
                )
            elif ev == "cont":
                self._file.write(data)
            elif ev == "end":
                self._file.seek(0)
                return (
                    "file",
                    (
                        self._name,
                        FileStorage(
                            self._file,
                            self._filename,
                            self._name,
                            headers=self._headers,
                        ),
                    ),
                )
            else:
                return event

        def feed(self, events):
            rv = []
            for event in events:
                v = self._feed_one(event)
                if v is not None:
                    rv.append(v)
            return rv

    def parse_lines(self, file, boundary, content_length, cap_at_buffer=True):
        """Generate parts of
        ``('begin_form', (headers, name))``
        ``('begin_file', (headers, name, filename))``
        ``('cont', bytestring)``
        ``('end', None)``

        Always obeys the grammar
        parts = ( begin_form cont* end |
                  begin_file cont* end )*
        """

        line_splitter = self.LineSplitter(self.buffer_size if cap_at_buffer else None)
        line_parser = self.LineParser(self, boundary)
        while True:
            buf = file.read(self.buffer_size)
            lines = line_splitter.feed(buf)
            parts = line_parser.feed(lines)
            for part in parts:
                yield part
            if buf == b"":
                break

    def parse_parts(self, file, boundary, content_length):
        """Generate ``('file', (name, val))`` and
        ``('form', (name, val))`` parts.
        """
        line_splitter = self.LineSplitter()
        line_parser = self.LineParser(self, boundary)
        part_parser = self.PartParser(self)
        file_writer = self.FileWriter(self, content_length)
        while True:
            buf = file.read(self.buffer_size)
            lines = line_splitter.feed(buf)
            parts = line_parser.feed(lines)
            events = part_parser.feed(parts)
            fevents = file_writer.feed(events)
            for event in fevents:
                yield event
            if buf == b"":
                break

    def parse(self, file, boundary, content_length):
        formstream, filestream = tee(
            self.parse_parts(file, boundary, content_length), 2
        )
        form = (p[1] for p in formstream if p[0] == "form")
        files = (p[1] for p in filestream if p[0] == "file")
        return self.cls(form), self.cls(files)


from . import exceptions
