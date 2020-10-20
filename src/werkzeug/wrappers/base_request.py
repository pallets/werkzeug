from functools import update_wrapper
from io import BytesIO
from typing import BinaryIO
from typing import Callable
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

from .._internal import _to_str
from .._internal import _wsgi_decoding_dance
from ..datastructures import CombinedMultiDict
from ..datastructures import EnvironHeaders
from ..datastructures import ImmutableList
from ..datastructures import ImmutableMultiDict
from ..datastructures import iter_multi_items
from ..datastructures import MultiDict
from ..formparser import default_stream_factory
from ..formparser import FormDataParser
from ..http import parse_cookie
from ..http import parse_list_header
from ..http import parse_options_header
from ..urls import url_decode
from ..utils import cached_property
from ..utils import environ_property
from ..wsgi import get_content_length
from ..wsgi import get_current_url
from ..wsgi import get_host
from ..wsgi import get_input_stream
from werkzeug.types import WSGIEnvironment

if TYPE_CHECKING:
    from werkzeug.wrappers.request import PlainRequest, Request  # noqa: F401
    from werkzeug.wsgi import LimitedStream  # noqa: F401


class BaseRequest:
    """Very basic request object.  This does not implement advanced stuff like
    entity tag parsing or cache controls.  The request object is created with
    the WSGI environment as first argument and will add itself to the WSGI
    environment as ``'werkzeug.request'`` unless it's created with
    `populate_request` set to False.

    There are a couple of mixins available that add additional functionality
    to the request object, there is also a class called `Request` which
    subclasses `BaseRequest` and all the important mixins.

    It's a good idea to create a custom subclass of the :class:`BaseRequest`
    and add missing functionality either via mixins or direct implementation.
    Here an example for such subclasses::

        from werkzeug.wrappers import BaseRequest, ETagRequestMixin

        class Request(BaseRequest, ETagRequestMixin):
            pass

    Request objects are **read only**.  As of 0.5 modifications are not
    allowed in any place.  Unlike the lower level parsing functions the
    request object will use immutable objects everywhere possible.

    Per default the request object will assume all the text data is `utf-8`
    encoded.  Please refer to :doc:`/unicode` for more details about
    customizing the behavior.

    Per default the request object will be added to the WSGI
    environment as `werkzeug.request` to support the debugging system.
    If you don't want that, set `populate_request` to `False`.

    If `shallow` is `True` the environment is initialized as shallow
    object around the environ.  Every operation that would modify the
    environ in any way (such as consuming form data) raises an exception
    unless the `shallow` attribute is explicitly set to `False`.  This
    is useful for middlewares where you don't want to consume the form
    data by accident.  A shallow request is not populated to the WSGI
    environment.

    .. versionchanged:: 0.5
       read-only mode was enforced by using immutables classes for all
       data.
    """

    #: the charset for the request, defaults to utf-8
    charset = "utf-8"

    #: the error handling procedure for errors, defaults to 'replace'
    encoding_errors = "replace"

    #: the maximum content length.  This is forwarded to the form data
    #: parsing function (:func:`parse_form_data`).  When set and the
    #: :attr:`form` or :attr:`files` attribute is accessed and the
    #: parsing fails because more than the specified value is transmitted
    #: a :exc:`~werkzeug.exceptions.RequestEntityTooLarge` exception is raised.
    #:
    #: Have a look at :doc:`/request_data` for more details.
    #:
    #: .. versionadded:: 0.5
    max_content_length = None

    #: the maximum form field size.  This is forwarded to the form data
    #: parsing function (:func:`parse_form_data`).  When set and the
    #: :attr:`form` or :attr:`files` attribute is accessed and the
    #: data in memory for post data is longer than the specified value a
    #: :exc:`~werkzeug.exceptions.RequestEntityTooLarge` exception is raised.
    #:
    #: Have a look at :doc:`/request_data` for more details.
    #:
    #: .. versionadded:: 0.5
    max_form_memory_size = None

    #: the class to use for `args` and `form`.  The default is an
    #: :class:`~werkzeug.datastructures.ImmutableMultiDict` which supports
    #: multiple values per key.  alternatively it makes sense to use an
    #: :class:`~werkzeug.datastructures.ImmutableOrderedMultiDict` which
    #: preserves order or a :class:`~werkzeug.datastructures.ImmutableDict`
    #: which is the fastest but only remembers the last key.  It is also
    #: possible to use mutable structures, but this is not recommended.
    #:
    #: .. versionadded:: 0.6
    parameter_storage_class = ImmutableMultiDict

    #: the type to be used for list values from the incoming WSGI environment.
    #: By default an :class:`~werkzeug.datastructures.ImmutableList` is used
    #: (for example for :attr:`access_list`).
    #:
    #: .. versionadded:: 0.6
    list_storage_class = ImmutableList

    #: The type to be used for dict values from the incoming WSGI
    #: environment. (For example for :attr:`cookies`.) By default an
    #: :class:`~werkzeug.datastructures.ImmutableMultiDict` is used.
    #:
    #: .. versionchanged:: 1.0.0
    #:     Changed to ``ImmutableMultiDict`` to support multiple values.
    #:
    #: .. versionadded:: 0.6
    dict_storage_class = ImmutableMultiDict

    #: The form data parser that shoud be used.  Can be replaced to customize
    #: the form date parsing.
    form_data_parser_class = FormDataParser

    #: Optionally a list of hosts that is trusted by this request.  By default
    #: all hosts are trusted which means that whatever the client sends the
    #: host is will be accepted.
    #:
    #: Because `Host` and `X-Forwarded-Host` headers can be set to any value by
    #: a malicious client, it is recommended to either set this property or
    #: implement similar validation in the proxy (if application is being run
    #: behind one).
    #:
    #: .. versionadded:: 0.9
    trusted_hosts = None

    #: Indicates whether the data descriptor should be allowed to read and
    #: buffer up the input stream.  By default it's enabled.
    #:
    #: .. versionadded:: 0.9
    disable_data_descriptor = False

    def __init__(
        self,
        environ: WSGIEnvironment,
        populate_request: bool = True,
        shallow: bool = False,
    ) -> None:
        self.environ = environ
        if populate_request and not shallow:
            self.environ["werkzeug.request"] = self
        self.shallow = shallow

    def __repr__(self) -> str:
        # make sure the __repr__ even works if the request was created
        # from an invalid WSGI environment.  If we display the request
        # in a debug session we don't want the repr to blow up.
        args = []
        try:
            args.append(f"'{self.url}'")
            args.append(f"[{self.method}]")
        except Exception:
            args.append("(invalid WSGI environ)")

        return f"<{type(self).__name__} {' '.join(args)}>"

    @property
    def url_charset(self) -> str:
        """The charset that is assumed for URLs.  Defaults to the value
        of :attr:`charset`.

        .. versionadded:: 0.6
        """
        return self.charset

    @classmethod
    def from_values(cls, *args, **kwargs):
        """Create a new request object based on the values provided.  If
        environ is given missing values are filled from there.  This method is
        useful for small scripts when you need to simulate a request from an URL.
        Do not use this method for unittesting, there is a full featured client
        object (:class:`Client`) that allows to create multipart requests,
        support for cookies etc.

        This accepts the same options as the
        :class:`~werkzeug.test.EnvironBuilder`.

        .. versionchanged:: 0.5
           This method now accepts the same arguments as
           :class:`~werkzeug.test.EnvironBuilder`.  Because of this the
           `environ` parameter is now called `environ_overrides`.

        :return: request object
        """
        from ..test import EnvironBuilder

        charset = kwargs.pop("charset", cls.charset)
        kwargs["charset"] = charset
        builder = EnvironBuilder(*args, **kwargs)
        try:
            return builder.get_request(cls)
        finally:
            builder.close()

    @classmethod
    def application(cls, f: Callable) -> Callable:
        """Decorate a function as responder that accepts the request as
        the last argument.  This works like the :func:`responder`
        decorator but the function is passed the request object as the
        last argument and the request object will be closed
        automatically::

            @Request.application
            def my_wsgi_app(request):
                return Response('Hello World!')

        As of Werkzeug 0.14 HTTP exceptions are automatically caught and
        converted to responses instead of failing.

        :param f: the WSGI callable to decorate
        :return: a new WSGI callable
        """
        #: return a callable that wraps the -2nd argument with the request
        #: and calls the function with all the arguments up to that one and
        #: the request.  The return value is then called with the latest
        #: two arguments.  This makes it possible to use this decorator for
        #: both standalone WSGI functions as well as bound methods and
        #: partially applied functions.
        from ..exceptions import HTTPException

        def application(*args):
            request = cls(args[-2])
            with request:
                try:
                    resp = f(*args[:-2] + (request,))
                except HTTPException as e:
                    resp = e.get_response(args[-2])
                return resp(*args[-2:])

        return update_wrapper(application, f)

    def _get_file_stream(
        self,
        total_content_length: int,
        content_type: Optional[str],
        filename: Optional[str] = None,
        content_length: Optional[int] = None,
    ) -> BinaryIO:
        """Called to get a stream for the file upload.

        This must provide a file-like class with `read()`, `readline()`
        and `seek()` methods that is both writeable and readable.

        The default implementation returns a temporary file if the total
        content length is higher than 500KB.  Because many browsers do not
        provide a content length for the files only the total content
        length matters.

        :param total_content_length: the total content length of all the
                                     data in the request combined.  This value
                                     is guaranteed to be there.
        :param content_type: the mimetype of the uploaded file.
        :param filename: the filename of the uploaded file.  May be `None`.
        :param content_length: the length of this file.  This value is usually
                               not provided because webbrowsers do not provide
                               this value.
        """
        return default_stream_factory(
            total_content_length=total_content_length,
            filename=filename,
            content_type=content_type,
            content_length=content_length,
        )

    @property
    def want_form_data_parsed(self) -> bool:
        """Returns True if the request method carries content.  As of
        Werkzeug 0.9 this will be the case if a content type is transmitted.

        .. versionadded:: 0.8
        """
        return bool(self.environ.get("CONTENT_TYPE"))

    def make_form_data_parser(self) -> FormDataParser:
        """Creates the form data parser. Instantiates the
        :attr:`form_data_parser_class` with some parameters.

        .. versionadded:: 0.8
        """
        return self.form_data_parser_class(
            self._get_file_stream,
            self.charset,
            self.encoding_errors,
            self.max_form_memory_size,
            self.max_content_length,
            self.parameter_storage_class,
        )

    def _load_form_data(self) -> None:
        """Method used internally to retrieve submitted data.  After calling
        this sets `form` and `files` on the request object to multi dicts
        filled with the incoming form data.  As a matter of fact the input
        stream will be empty afterwards.  You can also call this method to
        force the parsing of the form data.

        .. versionadded:: 0.8
        """
        # abort early if we have already consumed the stream
        if "form" in self.__dict__:
            return

        _assert_not_shallow(self)

        if self.want_form_data_parsed:
            content_type = self.environ.get("CONTENT_TYPE", "")
            content_length = get_content_length(self.environ)
            mimetype, options = parse_options_header(content_type)
            parser = self.make_form_data_parser()
            stream, form_headers, files = parser.parse(
                self._get_stream_for_parsing(), mimetype, content_length, options,
            )
            form = self.parameter_storage_class(
                (key, value.value) for key, value in iter_multi_items(form_headers)
            )
        else:
            stream = self.stream
            form = form_headers = self.parameter_storage_class()
            files = self.parameter_storage_class()

        # inject the values into the instance dict so that we bypass
        # our cached_property non-data descriptor.
        d = self.__dict__
        d["stream"] = stream
        d["form"] = form
        d["form_headers"] = form_headers
        d["files"] = files

    def _get_stream_for_parsing(self) -> BinaryIO:
        """This is the same as accessing :attr:`stream` with the difference
        that if it finds cached data from calling :meth:`get_data` first it
        will create a new stream out of the cached data.

        .. versionadded:: 0.9.3
        """
        cached_data = getattr(self, "_cached_data", None)

        if cached_data is not None:
            return BytesIO(cached_data)

        return self.stream

    def close(self) -> None:
        """Closes associated resources of this request object.  This
        closes all file handles explicitly.  You can also use the request
        object in a with statement which will automatically close it.

        .. versionadded:: 0.9
        """
        files = self.__dict__.get("files")
        for _key, value in iter_multi_items(files or ()):
            value.close()

    def __enter__(self) -> "Request":
        return self  # type: ignore

    def __exit__(self, exc_type: None, exc_value: None, tb: None) -> None:
        self.close()

    @cached_property
    def stream(self):
        """
        If the incoming form data was not encoded with a known mimetype
        the data is stored unmodified in this stream for consumption.  Most
        of the time it is a better idea to use :attr:`data` which will give
        you that data as a string.  The stream only returns the data once.

        Unlike :attr:`input_stream` this stream is properly guarded that you
        can't accidentally read past the length of the input.  Werkzeug will
        internally always refer to this stream to read data which makes it
        possible to wrap this object with a stream that does filtering.

        .. versionchanged:: 0.9
           This stream is now always available but might be consumed by the
           form parser later on.  Previously the stream was only set if no
           parsing happened.
        """
        _assert_not_shallow(self)
        return get_input_stream(self.environ)

    input_stream = environ_property(
        "wsgi.input",
        """The WSGI input stream.

        In general it's a bad idea to use this one because you can
        easily read past the boundary.  Use the :attr:`stream`
        instead.""",
    )

    @cached_property
    def args(self):
        """The parsed URL parameters (the part in the URL after the question
        mark).

        By default an
        :class:`~werkzeug.datastructures.ImmutableMultiDict`
        is returned from this function.  This can be changed by setting
        :attr:`parameter_storage_class` to a different type.  This might
        be necessary if the order of the form data is important.
        """
        return url_decode(
            self.environ.get("QUERY_STRING", "").encode("latin1"),
            self.url_charset,
            errors=self.encoding_errors,
            cls=self.parameter_storage_class,
        )

    @cached_property
    def data(self):
        """
        Contains the incoming request data as string in case it came with
        a mimetype Werkzeug does not handle.
        """

        if self.disable_data_descriptor:
            raise AttributeError("data descriptor is disabled")
        # XXX: this should eventually be deprecated.

        # We trigger form data parsing first which means that the descriptor
        # will not cache the data that would otherwise be .form or .files
        # data.  This restores the behavior that was there in Werkzeug
        # before 0.9.  New code should use :meth:`get_data` explicitly as
        # this will make behavior explicit.
        return self.get_data(parse_form_data=True)

    def get_data(
        self, cache: bool = True, as_text: bool = False, parse_form_data: bool = False,
    ) -> Union[str, bytes]:
        """This reads the buffered incoming data from the client into one
        bytes object.  By default this is cached but that behavior can be
        changed by setting `cache` to `False`.

        Usually it's a bad idea to call this method without checking the
        content length first as a client could send dozens of megabytes or more
        to cause memory problems on the server.

        Note that if the form data was already parsed this method will not
        return anything as form data parsing does not cache the data like
        this method does.  To implicitly invoke form data parsing function
        set `parse_form_data` to `True`.  When this is done the return value
        of this method will be an empty string if the form parser handles
        the data.  This generally is not necessary as if the whole data is
        cached (which is the default) the form parser will used the cached
        data to parse the form data.  Please be generally aware of checking
        the content length first in any case before calling this method
        to avoid exhausting server memory.

        If `as_text` is set to `True` the return value will be a decoded
        string.

        .. versionadded:: 0.9
        """
        rv = getattr(self, "_cached_data", None)
        if rv is None:
            if parse_form_data:
                self._load_form_data()
            rv = self.stream.read()
            if cache:
                self._cached_data = rv
        if as_text:
            rv = rv.decode(self.charset, self.encoding_errors)
        return rv

    @cached_property
    def form(self):
        """The form parameters, as a
        :class:`~werkzeug.datastructures.ImmutableMultiDict``. This will
        contain data if the content type is ``multipart/form-data`` or
        ``application/x-www-form-urlencoded``.

        ``form[name]`` will return the first value. Use
        ``getlist(name)`` to get a list of values. Accessing a key that
        doesn't exist will raise a 400 error (a
        :exc:`~werkzeug.exceptions.BadRequestKeyError`). Use
        ``get(name, default)`` to access an optional name. See
        :class:`~werkzeug.datastrcutures.MultiDict` for the full API.

        If the content type is ``multipart/form-data``, file uploads
        will be in :attr:`files`, not here. Extended information about
        form fields can be found in :attr:`form_headers`.
        """
        self._load_form_data()
        return self.form

    @cached_property
    def form_headers(self):
        """Extended information about form parameters. Commonly,
        ``multipart/form-data`` is used to upload files along with form
        data. Each part of the data can additionally have its own
        headers, although this requires a special client to produce.

        Similar to :attr:`files`, this exposes form parameters as
        :class:`~werkzeug.datastructures.FormFieldStorage` objects. Each
        object has a ``value`` as well as a ``headers`` attribute.

        .. versionadded:: 2.0
        """
        self._load_form_data()
        return self.form_headers

    @cached_property
    def values(self):
        """A :class:`werkzeug.datastructures.CombinedMultiDict` that combines
        :attr:`args` and :attr:`form`."""
        args = []
        for d in self.args, self.form:
            if not isinstance(d, MultiDict):
                d = MultiDict(d)
            args.append(d)
        return CombinedMultiDict(args)

    @cached_property
    def files(self):
        """:class:`~werkzeug.datastructures.MultiDict` object containing
        all uploaded files.  Each key in :attr:`files` is the name from the
        ``<input type="file" name="">``.  Each value in :attr:`files` is a
        Werkzeug :class:`~werkzeug.datastructures.FileStorage` object.

        It basically behaves like a standard file object you know from Python,
        with the difference that it also has a
        :meth:`~werkzeug.datastructures.FileStorage.save` function that can
        store the file on the filesystem.

        Note that :attr:`files` will only contain data if the request method was
        POST, PUT or PATCH and the ``<form>`` that posted to the request had
        ``enctype="multipart/form-data"``.  It will be empty otherwise.

        See the :class:`~werkzeug.datastructures.MultiDict` /
        :class:`~werkzeug.datastructures.FileStorage` documentation for
        more details about the used data structure.
        """
        self._load_form_data()
        return self.files

    @cached_property
    def cookies(self):
        """A :class:`dict` with the contents of all cookies transmitted with
        the request."""
        return parse_cookie(
            self.environ,
            self.charset,
            self.encoding_errors,
            cls=self.dict_storage_class,
        )

    @cached_property
    def headers(self):
        """The headers from the WSGI environ as immutable
        :class:`~werkzeug.datastructures.EnvironHeaders`.
        """
        return EnvironHeaders(self.environ)

    @cached_property
    def path(self) -> str:
        """Requested path. This works a bit like the regular path
        info in the WSGI environment but will always include a leading slash,
        even if the URL root is accessed.
        """
        raw_path = _wsgi_decoding_dance(
            self.environ.get("PATH_INFO") or "", self.charset, self.encoding_errors,
        )
        return "/" + raw_path.lstrip("/")

    @cached_property
    def full_path(self) -> str:
        """Requested path, including the query string."""
        return f"{self.path}?{_to_str(self.query_string, self.url_charset)}"

    @cached_property
    def script_root(self) -> str:
        """The root path of the script without the trailing slash."""
        raw_path = _wsgi_decoding_dance(
            self.environ.get("SCRIPT_NAME") or "", self.charset, self.encoding_errors,
        )
        return raw_path.rstrip("/")

    @cached_property
    def url(self):
        """The reconstructed current URL as IRI.
        See also: :attr:`trusted_hosts`.
        """
        return get_current_url(self.environ, trusted_hosts=self.trusted_hosts)

    @cached_property
    def base_url(self) -> str:
        """Like :attr:`url` but without the querystring
        See also: :attr:`trusted_hosts`.
        """
        return get_current_url(
            self.environ, strip_querystring=True, trusted_hosts=self.trusted_hosts,
        )

    @cached_property
    def url_root(self) -> str:
        """The full URL root (with hostname), this is the application
        root as IRI.
        See also: :attr:`trusted_hosts`.
        """
        return get_current_url(self.environ, True, trusted_hosts=self.trusted_hosts)

    @cached_property
    def host_url(self) -> str:
        """Just the host with scheme as IRI.
        See also: :attr:`trusted_hosts`.
        """
        return get_current_url(
            self.environ, host_only=True, trusted_hosts=self.trusted_hosts
        )

    @cached_property
    def host(self) -> str:
        """Just the host including the port if available.
        See also: :attr:`trusted_hosts`.
        """
        return get_host(self.environ, trusted_hosts=self.trusted_hosts)

    query_string = environ_property(
        "QUERY_STRING",
        "",
        read_only=True,
        load_func=lambda x: x.encode("latin1"),
        doc="The URL parameters as raw bytes.",
    )
    method = environ_property(
        "REQUEST_METHOD",
        "GET",
        read_only=True,
        load_func=lambda x: x.upper(),
        doc="The request method. (For example ``'GET'`` or ``'POST'``).",
    )

    @cached_property
    def access_route(self):
        """If a forwarded header exists this is a list of all ip addresses
        from the client ip to the last proxy server.
        """
        if "HTTP_X_FORWARDED_FOR" in self.environ:
            return self.list_storage_class(
                parse_list_header(self.environ["HTTP_X_FORWARDED_FOR"])
            )
        elif "REMOTE_ADDR" in self.environ:
            return self.list_storage_class([self.environ["REMOTE_ADDR"]])
        return self.list_storage_class()

    @property
    def remote_addr(self) -> str:
        """The remote address of the client."""
        return self.environ.get("REMOTE_ADDR")

    remote_user = environ_property(
        "REMOTE_USER",
        doc="""If the server supports user authentication, and the
        script is protected, this attribute contains the username the
        user has authenticated as.""",
    )
    scheme = environ_property(
        "wsgi.url_scheme",
        doc="""
        URL scheme (http or https).

        .. versionadded:: 0.7""",
    )
    is_secure = property(
        lambda self: self.environ["wsgi.url_scheme"] == "https",
        doc="`True` if the request is secure.",
    )
    is_multithread = environ_property(
        "wsgi.multithread",
        doc="""boolean that is `True` if the application is served by a
        multithreaded WSGI server.""",
    )
    is_multiprocess = environ_property(
        "wsgi.multiprocess",
        doc="""boolean that is `True` if the application is served by a
        WSGI server that spawns multiple processes.""",
    )
    is_run_once = environ_property(
        "wsgi.run_once",
        doc="""boolean that is `True` if the application will be
        executed only once in a process lifetime.  This is the case for
        CGI for example, but it's not guaranteed that the execution only
        happens one time.""",
    )


def _assert_not_shallow(
    request: Union["Request", "BaseRequest", "PlainRequest"]
) -> None:
    if request.shallow:
        raise RuntimeError(
            "A shallow request tried to consume form data. If you really"
            " want to do that, set `shallow` to False."
        )
