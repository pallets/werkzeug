from __future__ import annotations
import mimetypes
import sys
from collections import defaultdict
from http.cookiejar import CookieJar
from io import BufferedRandom, BytesIO
from itertools import chain
from random import random
from tempfile import TemporaryFile
from time import time
from urllib.request import Request as _UrllibRequest

from ._internal import _get_environ
from ._internal import _make_encode_wrapper
from ._internal import _to_bytes
from ._internal import _wsgi_encoding_dance
from .datastructures import CallbackDict
from .datastructures import CombinedMultiDict
from .datastructures import EnvironHeaders
from .datastructures import FileMultiDict
from .datastructures import Headers
from .datastructures import MultiDict
from .http import dump_cookie
from .http import dump_options_header
from .http import parse_options_header
from .urls import iri_to_uri
from .urls import url_encode
from .urls import url_fix
from .urls import url_parse
from .urls import url_unparse
from .urls import url_unquote
from .utils import get_content_type
from .wrappers import BaseRequest
from .wsgi import ClosingIterator
from .wsgi import get_current_url
from _pytest.capture import EncodedFile
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Type, Union
from werkzeug.datastructures import CombinedMultiDict, FileMultiDict, Headers, MultiDict
from werkzeug.debug import DebuggedApplication
from werkzeug.middleware.http_proxy import ProxyMiddleware
from werkzeug.wrappers.base_request import BaseRequest
from werkzeug.wrappers.base_response import BaseResponse
from werkzeug.wrappers.request import PlainRequest, Request
from werkzeug.wrappers.response import Response
from werkzeug.wsgi import ClosingIterator


def stream_encode_multipart(
    values: Union[MultiDict, CombinedMultiDict],
    use_tempfile: bool = True,
    threshold: int = 1024 * 500,
    boundary: None = None,
    charset: str = "utf-8",
) -> Union[Tuple[BufferedRandom, int, str], Tuple[BytesIO, int, str]]:
    """Encode a dict of values (either strings or file descriptors or
    :class:`FileStorage` objects.) into a multipart encoded string stored
    in a file descriptor.
    """
    if boundary is None:
        boundary = f"---------------WerkzeugFormPart_{time()}{random()}"
    _closure = [BytesIO(), 0, False]

    if use_tempfile:

        def write_binary(string):
            stream, total_length, on_disk = _closure
            if on_disk:
                stream.write(string)
            else:
                length = len(string)
                if length + _closure[1] <= threshold:
                    stream.write(string)
                else:
                    new_stream = TemporaryFile("wb+")
                    new_stream.write(stream.getvalue())
                    new_stream.write(string)
                    _closure[0] = new_stream
                    _closure[2] = True
                _closure[1] = total_length + length

    else:
        write_binary = _closure[0].write

    def write(string):
        write_binary(string.encode(charset))

    if not isinstance(values, MultiDict):
        values = MultiDict(values)

    for key, values in values.lists():
        for value in values:
            write(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"')
            reader = getattr(value, "read", None)
            if reader is not None:
                filename = getattr(value, "filename", getattr(value, "name", None))
                content_type = getattr(value, "content_type", None)
                if content_type is None:
                    content_type = (
                        filename
                        and mimetypes.guess_type(filename)[0]
                        or "application/octet-stream"
                    )
                if filename is not None:
                    write(f'; filename="{filename}"\r\n')
                else:
                    write("\r\n")
                write(f"Content-Type: {content_type}\r\n\r\n")
                while 1:
                    chunk = reader(16384)
                    if not chunk:
                        break
                    write_binary(chunk)
            else:
                if not isinstance(value, str):
                    value = str(value)

                value = _to_bytes(value, charset)
                write("\r\n\r\n")
                write_binary(value)
            write("\r\n")
    write(f"--{boundary}--\r\n")

    length = int(_closure[0].tell())
    _closure[0].seek(0)
    return _closure[0], length, boundary


def encode_multipart(values, boundary=None, charset="utf-8"):
    """Like `stream_encode_multipart` but returns a tuple in the form
    (``boundary``, ``data``) where data is bytes.
    """
    stream, length, boundary = stream_encode_multipart(
        values, use_tempfile=False, boundary=boundary, charset=charset
    )
    return boundary, stream.read()


class _TestCookieHeaders:

    """A headers adapter for cookielib
    """

    def __init__(self, headers: Union[List[Tuple[str, str]], Headers]) -> None:
        self.headers = headers

    def getheaders(self, name):
        headers = []
        name = name.lower()
        for k, v in self.headers:
            if k.lower() == name:
                headers.append(v)
        return headers

    def get_all(self, name: str, default: Optional[List[Any]] = None) -> List[str]:
        rv = []
        for k, v in self.headers:
            if k.lower() == name.lower():
                rv.append(v)
        return rv or default or []


class _TestCookieResponse:

    """Something that looks like a httplib.HTTPResponse, but is actually just an
    adapter for our test responses to make them available for cookielib.
    """

    def __init__(self, headers: Union[List[Tuple[str, str]], Headers]) -> None:
        self.headers = _TestCookieHeaders(headers)

    def info(self) -> _TestCookieHeaders:
        return self.headers


class _TestCookieJar(CookieJar):

    """A cookielib.CookieJar modified to inject and read cookie headers from
    and to wsgi environments, and wsgi application responses.
    """

    def inject_wsgi(self, environ: Dict[str, Any]) -> None:
        """Inject the cookies as client headers into the server's wsgi
        environment.
        """
        cvals = [f"{c.name}={c.value}" for c in self]

        if cvals:
            environ["HTTP_COOKIE"] = "; ".join(cvals)
        else:
            environ.pop("HTTP_COOKIE", None)

    def extract_wsgi(
        self, environ: Dict[str, Any], headers: Union[List[Tuple[str, str]], Headers]
    ) -> None:
        """Extract the server's set-cookie headers as cookies into the
        cookie jar.
        """
        self.extract_cookies(
            _TestCookieResponse(headers), _UrllibRequest(get_current_url(environ))
        )


def _iter_data(
    data: Any,
) -> Iterator[
    Union[
        Tuple[str, str],
        Tuple[str, Tuple[BytesIO, str]],
        Tuple[str, Tuple[BytesIO]],
        Tuple[str, BytesIO],
        Tuple[str, int],
    ]
]:
    """Iterates over a `dict` or :class:`MultiDict` yielding all keys and
    values.
    This is used to iterate over the data passed to the
    :class:`EnvironBuilder`.
    """
    if isinstance(data, MultiDict):
        for key, values in data.lists():
            for value in values:
                yield key, value
    else:
        for key, values in data.items():
            if isinstance(values, list):
                for value in values:
                    yield key, value
            else:
                yield key, values


class EnvironBuilder:
    """This class can be used to conveniently create a WSGI environment
    for testing purposes.  It can be used to quickly create WSGI environments
    or request objects from arbitrary data.

    The signature of this class is also used in some other places as of
    Werkzeug 0.5 (:func:`create_environ`, :meth:`BaseResponse.from_values`,
    :meth:`Client.open`).  Because of this most of the functionality is
    available through the constructor alone.

    Files and regular form data can be manipulated independently of each
    other with the :attr:`form` and :attr:`files` attributes, but are
    passed with the same argument to the constructor: `data`.

    `data` can be any of these values:

    -   a `str` or `bytes` object: The object is converted into an
        :attr:`input_stream`, the :attr:`content_length` is set and you have to
        provide a :attr:`content_type`.
    -   a `dict` or :class:`MultiDict`: The keys have to be strings. The values
        have to be either any of the following objects, or a list of any of the
        following objects:

        -   a :class:`file`-like object:  These are converted into
            :class:`FileStorage` objects automatically.
        -   a `tuple`:  The :meth:`~FileMultiDict.add_file` method is called
            with the key and the unpacked `tuple` items as positional
            arguments.
        -   a `str`:  The string is set as form data for the associated key.
    -   a file-like object: The object content is loaded in memory and then
        handled like a regular `str` or a `bytes`.

    :param path: the path of the request.  In the WSGI environment this will
                 end up as `PATH_INFO`.  If the `query_string` is not defined
                 and there is a question mark in the `path` everything after
                 it is used as query string.
    :param base_url: the base URL is a URL that is used to extract the WSGI
                     URL scheme, host (server name + server port) and the
                     script root (`SCRIPT_NAME`).
    :param query_string: an optional string or dict with URL parameters.
    :param method: the HTTP method to use, defaults to `GET`.
    :param input_stream: an optional input stream.  Do not specify this and
                         `data`.  As soon as an input stream is set you can't
                         modify :attr:`args` and :attr:`files` unless you
                         set the :attr:`input_stream` to `None` again.
    :param content_type: The content type for the request.  As of 0.5 you
                         don't have to provide this when specifying files
                         and form data via `data`.
    :param content_length: The content length for the request.  You don't
                           have to specify this when providing data via
                           `data`.
    :param errors_stream: an optional error stream that is used for
                          `wsgi.errors`.  Defaults to :data:`stderr`.
    :param multithread: controls `wsgi.multithread`.  Defaults to `False`.
    :param multiprocess: controls `wsgi.multiprocess`.  Defaults to `False`.
    :param run_once: controls `wsgi.run_once`.  Defaults to `False`.
    :param headers: an optional list or :class:`Headers` object of headers.
    :param data: a string or dict of form data or a file-object.
                 See explanation above.
    :param json: An object to be serialized and assigned to ``data``.
        Defaults the content type to ``"application/json"``.
        Serialized with the function assigned to :attr:`json_dumps`.
    :param environ_base: an optional dict of environment defaults.
    :param environ_overrides: an optional dict of environment overrides.
    :param charset: the charset used to encode string data.

    .. versionchanged:: 2.0.0
        ``REQUEST_URI`` and ``RAW_URI`` is the full raw URI including
        the query string, not only the path.

    .. versionadded:: 0.15
        The ``json`` param and :meth:`json_dumps` method.

    .. versionadded:: 0.15
        The environ has keys ``REQUEST_URI`` and ``RAW_URI`` containing
        the path before perecent-decoding. This is not part of the WSGI
        PEP, but many WSGI servers include it.

    .. versionchanged:: 0.6
       ``path`` and ``base_url`` can now be unicode strings that are
       encoded with :func:`iri_to_uri`.
    """

    #: the server protocol to use.  defaults to HTTP/1.1
    server_protocol = "HTTP/1.1"

    #: the wsgi version to use.  defaults to (1, 0)
    wsgi_version = (1, 0)

    #: the default request class for :meth:`get_request`
    request_class = BaseRequest

    import json

    #: The serialization function used when ``json`` is passed.
    json_dumps = staticmethod(json.dumps)
    del json

    def __init__(
        self,
        path: Union[str, bytes] = "/",
        base_url: Optional[str] = None,
        query_string: Optional[Union[str, Dict[str, str]]] = None,
        method: str = "GET",
        input_stream: Optional[BytesIO] = None,
        content_type: Optional[str] = None,
        content_length: Optional[Union[str, int]] = None,
        errors_stream: Optional[EncodedFile] = None,
        multithread: bool = False,
        multiprocess: bool = False,
        run_once: bool = False,
        headers: Optional[Union[Headers, Dict[str, str]]] = None,
        data: Optional[Any] = None,
        environ_base: Optional[Dict[str, str]] = None,
        environ_overrides: Optional[
            Union[
                Dict[str, int],
                Dict[str, Tuple[int, int]],
                Dict[str, Union[str, Tuple[int, int], BytesIO, EncodedFile, bool]],
                Dict[str, str],
            ]
        ] = None,
        charset: str = "utf-8",
        mimetype: Optional[str] = None,
        json: Optional[Union[List[int], Dict[str, str]]] = None,
    ) -> None:
        path_s = _make_encode_wrapper(path)
        if query_string is not None and path_s("?") in path:
            raise ValueError("Query string is defined in the path and as an argument")
        request_uri = url_parse(path)
        if query_string is None and path_s("?") in path:
            query_string = request_uri.query
        self.charset = charset
        self.path = iri_to_uri(request_uri.path)
        self.request_uri = path
        if base_url is not None:
            base_url = url_fix(iri_to_uri(base_url, charset), charset)
        self.base_url = base_url
        if isinstance(query_string, (bytes, str)):
            self.query_string = query_string
        else:
            if query_string is None:
                query_string = MultiDict()
            elif not isinstance(query_string, MultiDict):
                query_string = MultiDict(query_string)
            self.args = query_string
        self.method = method
        if headers is None:
            headers = Headers()
        elif not isinstance(headers, Headers):
            headers = Headers(headers)
        self.headers = headers
        if content_type is not None:
            self.content_type = content_type
        if errors_stream is None:
            errors_stream = sys.stderr
        self.errors_stream = errors_stream
        self.multithread = multithread
        self.multiprocess = multiprocess
        self.run_once = run_once
        self.environ_base = environ_base
        self.environ_overrides = environ_overrides
        self.input_stream = input_stream
        self.content_length = content_length
        self.closed = False

        if json is not None:
            if data is not None:
                raise TypeError("can't provide both json and data")

            data = self.json_dumps(json)

            if self.content_type is None:
                self.content_type = "application/json"

        if data:
            if input_stream is not None:
                raise TypeError("can't provide input stream and data")
            if hasattr(data, "read"):
                data = data.read()
            if isinstance(data, str):
                data = data.encode(self.charset)
            if isinstance(data, bytes):
                self.input_stream = BytesIO(data)
                if self.content_length is None:
                    self.content_length = len(data)
            else:
                for key, value in _iter_data(data):
                    if isinstance(value, (tuple, dict)) or hasattr(value, "read"):
                        self._add_file_from_data(key, value)
                    else:
                        self.form.setlistdefault(key).append(value)

        if mimetype is not None:
            self.mimetype = mimetype

    @classmethod
    def from_environ(
        cls,
        environ: Dict[str, Union[str, Tuple[int, int], BytesIO, EncodedFile, bool]],
        **kwargs,
    ) -> EnvironBuilder:
        """Turn an environ dict back into a builder. Any extra kwargs
        override the args extracted from the environ.

        .. versionadded:: 0.15
        """
        headers = Headers(EnvironHeaders(environ))
        out = {
            "path": environ["PATH_INFO"],
            "base_url": cls._make_base_url(
                environ["wsgi.url_scheme"], headers.pop("Host"), environ["SCRIPT_NAME"]
            ),
            "query_string": environ["QUERY_STRING"],
            "method": environ["REQUEST_METHOD"],
            "input_stream": environ["wsgi.input"],
            "content_type": headers.pop("Content-Type", None),
            "content_length": headers.pop("Content-Length", None),
            "errors_stream": environ["wsgi.errors"],
            "multithread": environ["wsgi.multithread"],
            "multiprocess": environ["wsgi.multiprocess"],
            "run_once": environ["wsgi.run_once"],
            "headers": headers,
        }
        out.update(kwargs)
        return cls(**out)

    def _add_file_from_data(
        self, key: str, value: Union[BytesIO, Tuple[BytesIO], Tuple[BytesIO, str]]
    ) -> None:
        """Called in the EnvironBuilder to add files from the data dict."""
        if isinstance(value, tuple):
            self.files.add_file(key, *value)
        else:
            self.files.add_file(key, value)

    @staticmethod
    def _make_base_url(scheme: str, host: str, script_root: str) -> str:
        return url_unparse((scheme, host, script_root, "", "")).rstrip("/") + "/"

    @property
    def base_url(self):
        """The base URL is used to extract the URL scheme, host name,
        port, and root path.
        """
        return self._make_base_url(self.url_scheme, self.host, self.script_root)

    @base_url.setter
    def base_url(self, value):
        if value is None:
            scheme = "http"
            netloc = "localhost"
            script_root = ""
        else:
            scheme, netloc, script_root, qs, anchor = url_parse(value)
            if qs or anchor:
                raise ValueError("base url must not contain a query string or fragment")
        self.script_root = script_root.rstrip("/")
        self.host = netloc
        self.url_scheme = scheme

    @property
    def content_type(self):
        """The content type for the request.  Reflected from and to
        the :attr:`headers`.  Do not set if you set :attr:`files` or
        :attr:`form` for auto detection.
        """
        ct = self.headers.get("Content-Type")
        if ct is None and not self._input_stream:
            if self._files:
                return "multipart/form-data"
            if self._form:
                return "application/x-www-form-urlencoded"
            return None
        return ct

    @content_type.setter
    def content_type(self, value):
        if value is None:
            self.headers.pop("Content-Type", None)
        else:
            self.headers["Content-Type"] = value

    @property
    def mimetype(self):
        """The mimetype (content type without charset etc.)

        .. versionadded:: 0.14
        """
        ct = self.content_type
        return ct.split(";")[0].strip() if ct else None

    @mimetype.setter
    def mimetype(self, value):
        self.content_type = get_content_type(value, self.charset)

    @property
    def mimetype_params(self):
        """ The mimetype parameters as dict.  For example if the
        content type is ``text/html; charset=utf-8`` the params would be
        ``{'charset': 'utf-8'}``.

        .. versionadded:: 0.14
        """

        def on_update(d):
            self.headers["Content-Type"] = dump_options_header(self.mimetype, d)

        d = parse_options_header(self.headers.get("content-type", ""))[1]
        return CallbackDict(d, on_update)

    @property
    def content_length(self):
        """The content length as integer.  Reflected from and to the
        :attr:`headers`.  Do not set if you set :attr:`files` or
        :attr:`form` for auto detection.
        """
        return self.headers.get("Content-Length", type=int)

    @content_length.setter
    def content_length(self, value):
        if value is None:
            self.headers.pop("Content-Length", None)
        else:
            self.headers["Content-Length"] = str(value)

    def _get_form(
        self, name: str, storage: Union[Type[FileMultiDict], Type[MultiDict]]
    ) -> Union[MultiDict, FileMultiDict]:
        """Common behavior for getting the :attr:`form` and
        :attr:`files` properties.

        :param name: Name of the internal cached attribute.
        :param storage: Storage class used for the data.
        """
        if self.input_stream is not None:
            raise AttributeError("an input stream is defined")

        rv = getattr(self, name)

        if rv is None:
            rv = storage()
            setattr(self, name, rv)

        return rv

    def _set_form(self, name, value):
        """Common behavior for setting the :attr:`form` and
        :attr:`files` properties.

        :param name: Name of the internal cached attribute.
        :param value: Value to assign to the attribute.
        """
        self._input_stream = None
        setattr(self, name, value)

    @property
    def form(self):
        """A :class:`MultiDict` of form values."""
        return self._get_form("_form", MultiDict)

    @form.setter
    def form(self, value):
        self._set_form("_form", value)

    @property
    def files(self):
        """A :class:`FileMultiDict` of uploaded files. Use
        :meth:`~FileMultiDict.add_file` to add new files.
        """
        return self._get_form("_files", FileMultiDict)

    @files.setter
    def files(self, value):
        self._set_form("_files", value)

    @property
    def input_stream(self):
        """An optional input stream. This is mutually exclusive with
        setting :attr:`form` and :attr:`files`, setting it will clear
        those. Do not provide this if the method is not ``POST`` or
        another method that has a body.
        """
        return self._input_stream

    @input_stream.setter
    def input_stream(self, value):
        self._input_stream = value
        self._form = None
        self._files = None

    @property
    def query_string(self):
        """The query string.  If you set this to a string
        :attr:`args` will no longer be available.
        """
        if self._query_string is None:
            if self._args is not None:
                return url_encode(self._args, charset=self.charset)
            return ""
        return self._query_string

    @query_string.setter
    def query_string(self, value):
        self._query_string = value
        self._args = None

    @property
    def args(self):
        """The URL arguments as :class:`MultiDict`."""
        if self._query_string is not None:
            raise AttributeError("a query string is defined")
        if self._args is None:
            self._args = MultiDict()
        return self._args

    @args.setter
    def args(self, value):
        self._query_string = None
        self._args = value

    @property
    def server_name(self) -> str:
        """The server name (read-only, use :attr:`host` to set)"""
        return self.host.split(":", 1)[0]

    @property
    def server_port(self) -> int:
        """The server port as integer (read-only, use :attr:`host` to set)"""
        pieces = self.host.split(":", 1)
        if len(pieces) == 2 and pieces[1].isdigit():
            return int(pieces[1])
        if self.url_scheme == "https":
            return 443
        return 80

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """Closes all files.  If you put real :class:`file` objects into the
        :attr:`files` dict you can call this method to automatically close
        them all in one go.
        """
        if self.closed:
            return
        try:
            files = self.files.values()
        except AttributeError:
            files = ()
        for f in files:
            try:
                f.close()
            except Exception:
                pass
        self.closed = True

    def get_environ(self) -> Dict[str, Any]:
        """Return the built environ.

        .. versionchanged:: 0.15
            The content type and length headers are set based on
            input stream detection. Previously this only set the WSGI
            keys.
        """
        input_stream = self.input_stream
        content_length = self.content_length

        mimetype = self.mimetype
        content_type = self.content_type

        if input_stream is not None:
            start_pos = input_stream.tell()
            input_stream.seek(0, 2)
            end_pos = input_stream.tell()
            input_stream.seek(start_pos)
            content_length = end_pos - start_pos
        elif mimetype == "multipart/form-data":
            values = CombinedMultiDict([self.form, self.files])
            input_stream, content_length, boundary = stream_encode_multipart(
                values, charset=self.charset
            )
            content_type = f'{mimetype}; boundary="{boundary}"'
        elif mimetype == "application/x-www-form-urlencoded":
            values = url_encode(self.form, charset=self.charset)
            values = values.encode("ascii")
            content_length = len(values)
            input_stream = BytesIO(values)
        else:
            input_stream = BytesIO()

        result = {}
        if self.environ_base:
            result.update(self.environ_base)

        def _path_encode(x):
            return _wsgi_encoding_dance(url_unquote(x, self.charset), self.charset)

        qs = _wsgi_encoding_dance(self.query_string)

        result.update(
            {
                "REQUEST_METHOD": self.method,
                "SCRIPT_NAME": _path_encode(self.script_root),
                "PATH_INFO": _path_encode(self.path),
                "QUERY_STRING": qs,
                # Non-standard, added by mod_wsgi, uWSGI
                "REQUEST_URI": _wsgi_encoding_dance(self.request_uri),
                # Non-standard, added by gunicorn
                "RAW_URI": _wsgi_encoding_dance(self.request_uri),
                "SERVER_NAME": self.server_name,
                "SERVER_PORT": str(self.server_port),
                "HTTP_HOST": self.host,
                "SERVER_PROTOCOL": self.server_protocol,
                "wsgi.version": self.wsgi_version,
                "wsgi.url_scheme": self.url_scheme,
                "wsgi.input": input_stream,
                "wsgi.errors": self.errors_stream,
                "wsgi.multithread": self.multithread,
                "wsgi.multiprocess": self.multiprocess,
                "wsgi.run_once": self.run_once,
            }
        )

        headers = self.headers.copy()

        if content_type is not None:
            result["CONTENT_TYPE"] = content_type
            headers.set("Content-Type", content_type)

        if content_length is not None:
            result["CONTENT_LENGTH"] = str(content_length)
            headers.set("Content-Length", content_length)

        combined_headers = defaultdict(list)

        for key, value in headers.to_wsgi_list():
            combined_headers[f"HTTP_{key.upper().replace('-', '_')}"].append(value)

        for key, values in combined_headers.items():
            result[key] = ", ".join(values)

        if self.environ_overrides:
            result.update(self.environ_overrides)

        return result

    def get_request(
        self, cls: Optional[Union[Type[Request], Type[PlainRequest]]] = None
    ) -> Union[Request, BaseRequest, PlainRequest]:
        """Returns a request with the data.  If the request class is not
        specified :attr:`request_class` is used.

        :param cls: The request wrapper to use.
        """
        if cls is None:
            cls = self.request_class
        return cls(self.get_environ())


class ClientRedirectError(Exception):
    """If a redirect loop is detected when using follow_redirects=True with
    the :cls:`Client`, then this exception is raised.
    """


class Client:
    """This class allows you to send requests to a wrapped application.

    The response wrapper can be a class or factory function that takes
    three arguments: app_iter, status and headers.  The default response
    wrapper just returns a tuple.

    Example::

        class ClientResponse(BaseResponse):
            ...

        client = Client(MyApplication(), response_wrapper=ClientResponse)

    The use_cookies parameter indicates whether cookies should be stored and
    sent for subsequent requests. This is True by default, but passing False
    will disable this behaviour.

    If you want to request some subdomain of your application you may set
    `allow_subdomain_redirects` to `True` as if not no external redirects
    are allowed.

    .. versionadded:: 0.5
       `use_cookies` is new in this version.  Older versions did not provide
       builtin cookie support.

    .. versionadded:: 0.14
       The `mimetype` parameter was added.

    .. versionadded:: 0.15
        The ``json`` parameter.
    """

    def __init__(
        self,
        application: Union[ProxyMiddleware, DebuggedApplication, Callable, Response],
        response_wrapper: Optional[Union[Type[Response], Type[BaseResponse]]] = None,
        use_cookies: bool = True,
        allow_subdomain_redirects: bool = False,
    ) -> None:
        self.application = application
        self.response_wrapper = response_wrapper
        if use_cookies:
            self.cookie_jar = _TestCookieJar()
        else:
            self.cookie_jar = None
        self.allow_subdomain_redirects = allow_subdomain_redirects

    def set_cookie(
        self,
        server_name: str,
        key: str,
        value: str = "",
        max_age: None = None,
        expires: None = None,
        path: str = "/",
        domain: None = None,
        secure: None = None,
        httponly: bool = False,
        samesite: None = None,
        charset: str = "utf-8",
    ) -> None:
        """Sets a cookie in the client's cookie jar.  The server name
        is required and has to match the one that is also passed to
        the open call.
        """
        assert self.cookie_jar is not None, "cookies disabled"
        header = dump_cookie(
            key,
            value,
            max_age,
            expires,
            path,
            domain,
            secure,
            httponly,
            charset,
            samesite=samesite,
        )
        environ = create_environ(path, base_url=f"http://{server_name}")
        headers = [("Set-Cookie", header)]
        self.cookie_jar.extract_wsgi(environ, headers)

    def delete_cookie(self, server_name, key, path="/", domain=None):
        """Deletes a cookie in the test client."""
        self.set_cookie(
            server_name, key, expires=0, max_age=0, path=path, domain=domain
        )

    def run_wsgi_app(
        self,
        environ: Dict[str, Union[str, Tuple[int, int], BytesIO, EncodedFile, bool]],
        buffered: bool = False,
    ) -> Union[Tuple[ClosingIterator, str, Headers], Tuple[chain, str, Headers]]:
        """Runs the wrapped WSGI app with the given environment."""
        if self.cookie_jar is not None:
            self.cookie_jar.inject_wsgi(environ)
        rv = run_wsgi_app(self.application, environ, buffered=buffered)
        if self.cookie_jar is not None:
            self.cookie_jar.extract_wsgi(environ, rv[2])
        return rv

    def resolve_redirect(self, response, new_location, environ, buffered=False):
        """Perform a new request to the location given by the redirect
        response to the previous request.
        """
        scheme, netloc, path, qs, anchor = url_parse(new_location)
        builder = EnvironBuilder.from_environ(environ, query_string=qs)

        to_name_parts = netloc.split(":", 1)[0].split(".")
        from_name_parts = builder.server_name.split(".")

        if to_name_parts != [""]:
            # The new location has a host, use it for the base URL.
            builder.url_scheme = scheme
            builder.host = netloc
        else:
            # A local redirect with autocorrect_location_header=False
            # doesn't have a host, so use the request's host.
            to_name_parts = from_name_parts

        # Explain why a redirect to a different server name won't be followed.
        if to_name_parts != from_name_parts:
            if to_name_parts[-len(from_name_parts) :] == from_name_parts:
                if not self.allow_subdomain_redirects:
                    raise RuntimeError("Following subdomain redirects is not enabled.")
            else:
                raise RuntimeError("Following external redirects is not supported.")

        path_parts = path.split("/")
        root_parts = builder.script_root.split("/")

        if path_parts[: len(root_parts)] == root_parts:
            # Strip the script root from the path.
            builder.path = path[len(builder.script_root) :]
        else:
            # The new location is not under the script root, so use the
            # whole path and clear the previous root.
            builder.path = path
            builder.script_root = ""

        status_code = int(response[1].split(None, 1)[0])

        # Only 307 and 308 preserve all of the original request.
        if status_code not in {307, 308}:
            # HEAD is preserved, everything else becomes GET.
            if builder.method != "HEAD":
                builder.method = "GET"

            # Clear the body and the headers that describe it.
            builder.input_stream = None
            builder.content_type = None
            builder.content_length = None
            builder.headers.pop("Transfer-Encoding", None)

        # Disable the response wrapper while handling redirects. Not
        # thread safe, but the client should not be shared anyway.
        old_response_wrapper = self.response_wrapper
        self.response_wrapper = None

        try:
            return self.open(builder, as_tuple=True, buffered=buffered)
        finally:
            self.response_wrapper = old_response_wrapper

    def open(
        self, *args, **kwargs
    ) -> Union[
        Tuple[ClosingIterator, str, Headers],
        BaseResponse,
        Response,
        Tuple[
            Dict[str, Union[str, Tuple[int, int], BytesIO, EncodedFile, bool]],
            Tuple[ClosingIterator, str, Headers],
        ],
    ]:
        """Takes the same arguments as the :class:`EnvironBuilder` class with
        some additions:  You can provide a :class:`EnvironBuilder` or a WSGI
        environment as only argument instead of the :class:`EnvironBuilder`
        arguments and two optional keyword arguments (`as_tuple`, `buffered`)
        that change the type of the return value or the way the application is
        executed.

        .. versionchanged:: 0.5
           If a dict is provided as file in the dict for the `data` parameter
           the content type has to be called `content_type` now instead of
           `mimetype`.  This change was made for consistency with
           :class:`werkzeug.FileWrapper`.

            The `follow_redirects` parameter was added to :func:`open`.

        Additional parameters:

        :param as_tuple: Returns a tuple in the form ``(environ, result)``
        :param buffered: Set this to True to buffer the application run.
                         This will automatically close the application for
                         you as well.
        :param follow_redirects: Set this to True if the `Client` should
                                 follow HTTP redirects.
        """
        as_tuple = kwargs.pop("as_tuple", False)
        buffered = kwargs.pop("buffered", False)
        follow_redirects = kwargs.pop("follow_redirects", False)
        environ = None
        if not kwargs and len(args) == 1:
            if isinstance(args[0], EnvironBuilder):
                environ = args[0].get_environ()
            elif isinstance(args[0], dict):
                environ = args[0]
        if environ is None:
            builder = EnvironBuilder(*args, **kwargs)
            try:
                environ = builder.get_environ()
            finally:
                builder.close()

        response = self.run_wsgi_app(environ.copy(), buffered=buffered)

        # handle redirects
        redirect_chain = []
        while 1:
            status_code = int(response[1].split(None, 1)[0])
            if (
                status_code not in {301, 302, 303, 305, 307, 308}
                or not follow_redirects
            ):
                break

            # Exhaust intermediate response bodies to ensure middleware
            # that returns an iterator runs any cleanup code.
            if not buffered:
                for _ in response[0]:
                    pass

            new_location = response[2]["location"]
            new_redirect_entry = (new_location, status_code)
            if new_redirect_entry in redirect_chain:
                raise ClientRedirectError("loop detected")
            redirect_chain.append(new_redirect_entry)
            environ, response = self.resolve_redirect(
                response, new_location, environ, buffered=buffered
            )

        if self.response_wrapper is not None:
            response = self.response_wrapper(*response)
        if as_tuple:
            return environ, response
        return response

    def get(
        self, *args, **kw
    ) -> Union[Tuple[ClosingIterator, str, Headers], BaseResponse, Response]:
        """Like open but method is enforced to GET."""
        kw["method"] = "GET"
        return self.open(*args, **kw)

    def patch(self, *args, **kw):
        """Like open but method is enforced to PATCH."""
        kw["method"] = "PATCH"
        return self.open(*args, **kw)

    def post(self, *args, **kw) -> Union[BaseResponse, Response]:
        """Like open but method is enforced to POST."""
        kw["method"] = "POST"
        return self.open(*args, **kw)

    def head(self, *args, **kw):
        """Like open but method is enforced to HEAD."""
        kw["method"] = "HEAD"
        return self.open(*args, **kw)

    def put(self, *args, **kw):
        """Like open but method is enforced to PUT."""
        kw["method"] = "PUT"
        return self.open(*args, **kw)

    def delete(self, *args, **kw) -> Response:
        """Like open but method is enforced to DELETE."""
        kw["method"] = "DELETE"
        return self.open(*args, **kw)

    def options(self, *args, **kw):
        """Like open but method is enforced to OPTIONS."""
        kw["method"] = "OPTIONS"
        return self.open(*args, **kw)

    def trace(self, *args, **kw):
        """Like open but method is enforced to TRACE."""
        kw["method"] = "TRACE"
        return self.open(*args, **kw)

    def __repr__(self):
        return f"<{type(self).__name__} {self.application!r}>"


def create_environ(*args, **kwargs):
    """Create a new WSGI environ dict based on the values passed.  The first
    parameter should be the path of the request which defaults to '/'.  The
    second one can either be an absolute path (in that case the host is
    localhost:80) or a full path to the request with scheme, netloc port and
    the path to the script.

    This accepts the same arguments as the :class:`EnvironBuilder`
    constructor.

    .. versionchanged:: 0.5
       This function is now a thin wrapper over :class:`EnvironBuilder` which
       was added in 0.5.  The `headers`, `environ_base`, `environ_overrides`
       and `charset` parameters were added.
    """
    builder = EnvironBuilder(*args, **kwargs)
    try:
        return builder.get_environ()
    finally:
        builder.close()


def run_wsgi_app(
    app: Any, environ: Any, buffered: bool = False
) -> Union[
    Tuple[ClosingIterator, str, Headers],
    Tuple[List[str], str, Headers],
    Tuple[chain, str, Headers],
    Tuple[List[Any], str, Headers],
    Tuple[List[bytes], str, Headers],
]:
    """Return a tuple in the form (app_iter, status, headers) of the
    application output.  This works best if you pass it an application that
    returns an iterator all the time.

    Sometimes applications may use the `write()` callable returned
    by the `start_response` function.  This tries to resolve such edge
    cases automatically.  But if you don't get the expected output you
    should set `buffered` to `True` which enforces buffering.

    If passed an invalid WSGI application the behavior of this function is
    undefined.  Never pass non-conforming WSGI applications to this function.

    :param app: the application to execute.
    :param buffered: set to `True` to enforce buffering.
    :return: tuple in the form ``(app_iter, status, headers)``
    """
    environ = _get_environ(environ)
    response = []
    buffer = []

    def start_response(status, headers, exc_info=None):
        if exc_info:
            try:
                raise exc_info[1].with_traceback(exc_info[2])
            finally:
                exc_info = None
        response[:] = [status, headers]
        return buffer.append

    app_rv = app(environ, start_response)
    close_func = getattr(app_rv, "close", None)
    app_iter = iter(app_rv)

    # when buffering we emit the close call early and convert the
    # application iterator into a regular list
    if buffered:
        try:
            app_iter = list(app_iter)
        finally:
            if close_func is not None:
                close_func()

    # otherwise we iterate the application iter until we have a response, chain
    # the already received data with the already collected data and wrap it in
    # a new `ClosingIterator` if we need to restore a `close` callable from the
    # original return value.
    else:
        for item in app_iter:
            buffer.append(item)
            if response:
                break
        if buffer:
            app_iter = chain(buffer, app_iter)
        if close_func is not None and app_iter is not app_rv:
            app_iter = ClosingIterator(app_iter, close_func)

    return app_iter, response[0], Headers(response[1])
