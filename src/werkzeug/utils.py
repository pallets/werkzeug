from __future__ import annotations

import io
import mimetypes
import os
import pkgutil
import re
import sys
import typing as t
import unicodedata
from datetime import datetime
from functools import update_wrapper
from time import time
from urllib.parse import quote

from markupsafe import escape

from ._internal import _missing
from .datastructures.cache_control import ResponseCacheControl
from .datastructures.etag import ETag
from .datastructures.headers import Headers
from .exceptions import HTTPException
from .exceptions import NotFound
from .security import _windows_device_files
from .security import safe_join
from .wsgi import wrap_file

if t.TYPE_CHECKING:
    import typing_extensions as te
    from _typeshed.wsgi import WSGIEnvironment

    from .wrappers.response import Response

T = t.TypeVar("T")

_entity_re = re.compile(r"&([^;]+);")
_filename_ascii_strip_re = re.compile(r"[^A-Za-z0-9_.-]")


class cached_property(property, t.Generic[T]):
    """A :func:`property` that is only evaluated once. Subsequent access
    returns the cached value. Setting the property sets the cached
    value. Deleting the property clears the cached value, accessing it
    again will evaluate it again.

    .. code-block:: python

        class Example:
            @cached_property
            def value(self):
                # calculate something important here
                return 42

        e = Example()
        e.value  # evaluates
        e.value  # uses cache
        e.value = 16  # sets cache
        del e.value  # clears cache

    If the class defines ``__slots__``, it must add ``_cache_{name}`` as
    a slot. Alternatively, it can add ``__dict__``, but that's usually
    not desirable.

    .. versionchanged:: 2.1
        Works with ``__slots__``.

    .. versionchanged:: 2.0
        ``del obj.name`` clears the cached value.
    """

    def __init__(
        self,
        fget: t.Callable[[t.Any], T],
        name: str | None = None,
        doc: str | None = None,
    ) -> None:
        update_wrapper(self, fget)  # type: ignore[arg-type]
        super().__init__(fget, doc=doc)

        if name is not None:
            self.__name__ = name

        self.slot_name = f"_cache_{self.__name__}"

    @t.overload
    def __get__(self, obj: None, cls: type[t.Any], /) -> te.Self: ...
    @t.overload
    def __get__(self, obj: t.Any, cls: type[t.Any] | None = ..., /) -> T: ...
    def __get__(
        self, obj: t.Any | None = None, cls: type[t.Any] | None = None, /
    ) -> T | te.Self:
        if obj is None:
            return self

        obj_dict = getattr(obj, "__dict__", None)

        if obj_dict is not None:
            value: T = obj_dict.get(self.__name__, _missing)
        else:
            value = getattr(obj, self.slot_name, _missing)  # type: ignore[arg-type]

        if value is _missing:
            value = self.fget(obj)  # type: ignore[misc]

            if obj_dict is not None:
                obj.__dict__[self.__name__] = value
            else:
                setattr(obj, self.slot_name, value)

        return value

    def __set__(self, obj: object, value: T) -> None:
        if hasattr(obj, "__dict__"):
            obj.__dict__[self.__name__] = value
        else:
            setattr(obj, self.slot_name, value)

    def __delete__(self, obj: t.Any) -> None:
        if hasattr(obj, "__dict__"):
            obj.__dict__.pop(self.__name__, None)
        else:
            setattr(obj, self.slot_name, _missing)


# https://cgit.freedesktop.org/xdg/shared-mime-info/tree/freedesktop.org.xml.in
# https://www.iana.org/assignments/media-types/media-types.xhtml
# Types listed in the XDG mime info that have a charset in the IANA registration.
_charset_mimetypes = {
    "application/ecmascript",
    "application/javascript",
    "application/sql",
    "application/xml",
    "application/xml-dtd",
    "application/xml-external-parsed-entity",
}


def get_content_type(mimetype: str, charset: str) -> str:
    """Returns the full content type string with charset for a mimetype.

    If the mimetype represents text, the charset parameter will be
    appended, otherwise the mimetype is returned unchanged.

    :param mimetype: The mimetype to be used as content type.
    :param charset: The charset to be appended for text mimetypes.
    :return: The content type.

    .. versionchanged:: 0.15
        Any type that ends with ``+xml`` gets a charset, not just those
        that start with ``application/``. Known text types such as
        ``application/javascript`` are also given charsets.
    """
    if (
        mimetype.startswith("text/")
        or mimetype in _charset_mimetypes
        or mimetype.endswith("+xml")
    ):
        mimetype += f"; charset={charset}"

    return mimetype


def secure_filename(filename: str) -> str:
    """Validate and modify a filename so that it is safe to use on a regular
    filesystem and in :func:`os.path.join`. This may produce an empty string if
    nothing in the filename could be safely preserved.

    Only the ASCII letters, digits, and ``._-`` characters are allowed, all
    others are removed or replaced. Unicode characters are decomposed and
    replaced with ASCII equivalents according to NFKD. ``/`` (and ``\\`` on
    Windows) and whitespace, are replaced with ``_``. Surrounding ``._``
    characters are removed.

    On Windows, special device names such as ``CON`` and ``NUL`` will be
    prefixed with ``_`` to avoid access.

    This only considers the filename, it does not validate if the file does or
    does not exist, if it is a symlink, or other properties of the file.

    :param filename: The filename to validate and modify.

    .. versionadded:: 0.5
    """
    # decompose combined chars, replace compat chars
    filename = unicodedata.normalize("NFKD", filename)
    # only keep ASCII chars
    filename = filename.encode("ascii", "ignore").decode("ascii")

    for sep in os.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")

    # replace any whitespace with _
    filename = "_".join(filename.split())
    # only allow ASCII letters, numbers, and _.-
    filename = _filename_ascii_strip_re.sub("", filename)
    # remove surrounding ._, left behind after replacing slash in ../
    filename = filename.strip("._")

    # prefix special device names on Windows
    if (
        os.name == "nt"
        and filename.partition(".")[0].strip().upper() in _windows_device_files
    ):
        filename = f"_{filename}"

    return filename


def redirect(
    location: str, code: int = 303, Response: type[Response] | None = None
) -> Response:
    """Create a response that redirects the client to the target location.

    The default ``303 See Other`` status code instructs the client to make a
    ``GET`` request to the target, regardless of what method the current request
    is. This produces the correct result for the common use cases: page redirects
    and form success. The status codes you're likely to use are:

    -   ``303 See Other`` always uses a ``GET`` request.
    -   ``307 Temporary Redirect`` preserves the current method.
    -   ``308 Permanent Redirect`` preserves the current method, and instructs
        the client to permanently apply the result. This is hard to undo once
        you've sent it, so be sure the permanence is what you want.

    Two older codes, ``302 Found`` and ``301 Moved Permanently``, are
    superseded by ``307`` and ``308`` respectively. They were not consistently
    implemented by clients, which tend to switch ``POST`` to ``GET`` but
    preserve other methods. Prefer using ``303``, ``307``, and ``308`` to get
    the exact behavior you intend. Other ``3xx`` codes are either not defined or
    have specific use cases.

    :param location: The URL to redirect to. The client will interpret a
        relative URL (without the host) as relative to the host it's accessing.
    :param code: The redirect status code. This affects how the client issues
        the next request. Defaults to ``303``.
    :param Response: The response class. Defaults to
        :class:`werkzeug.wrappers.Response`.

    .. versionchanged:: 3.2
        ``code`` defaults to 303 instead of 302.

    .. versionchanged:: 0.10
        Added the ``response`` parameter.

    .. versionchanged:: 0.6
        ``location`` can contain Unicode characters.
    """
    if Response is None:
        from .wrappers import Response

    html_location = escape(location)
    response = Response(  # type: ignore[misc]
        "<!doctype html>\n"
        "<html lang=en>\n"
        "<title>Redirecting...</title>\n"
        "<h1>Redirecting...</h1>\n"
        "<p>You should be redirected automatically to the target URL: "
        f'<a href="{html_location}">{html_location}</a>. If not, click the link.\n',
        code,
        mimetype="text/html",
    )
    response.headers["Location"] = location
    return response


def append_slash_redirect(environ: WSGIEnvironment, code: int = 308) -> Response:
    """Redirect to the current URL with a slash appended.

    If the current URL is ``/user/42``, the redirect URL will be
    ``42/``. When joined to the current URL during response
    processing or by the browser, this will produce ``/user/42/``.

    The behavior is undefined if the path ends with a slash already. If
    called unconditionally on a URL, it may produce a redirect loop.

    :param environ: Use the path and query from this WSGI environment
        to produce the redirect URL.
    :param code: the status code for the redirect.

    .. versionchanged:: 2.1
        Produce a relative URL that only modifies the last segment.
        Relevant when the current path has multiple segments.

    .. versionchanged:: 2.1
        The default status code is 308 instead of 301. This preserves
        the request method and body.
    """
    tail = environ["PATH_INFO"].rpartition("/")[2]

    if not tail:
        new_path = "./"
    else:
        new_path = f"{tail}/"

    query_string = environ.get("QUERY_STRING")

    if query_string:
        new_path = f"{new_path}?{query_string}"

    return redirect(new_path, code)


def send_file(
    path_or_file: os.PathLike[str] | str | t.IO[bytes],
    environ: WSGIEnvironment,
    mimetype: str | None = None,
    as_attachment: bool = False,
    download_name: str | None = None,
    conditional: bool = True,
    etag: bool | ETag | str = True,
    last_modified: datetime | int | float | None = None,
    max_age: int
    | t.Callable[[os.PathLike[str] | str | None], int | None]
    | None = None,
    use_x_sendfile: bool = False,
    response_class: type[Response] | None = None,
    _root_path: os.PathLike[str] | str | None = None,
) -> Response:
    """Send the contents of a file to the client.

    The first argument can be a file path or a file-like object in ``rb`` mode.
    Paths are preferred in most cases because Werkzeug can manage the file.
    Passing a file-like object is mostly useful when building a file in memory
    with :class:`io.BytesIO`. If the file is seekable, its position will be set
    to the beginning.

    Never pass a path provided by a user. The path is assumed to be trusted, so
    a user could craft a path to access a file you didn't intend. Use
    :func:`send_from_directory` to safely serve user-provided paths.

    If the WSGI server provides ``environ["wsgi.file_wrapper"]``, it is
    used. Alternatively, if the HTTP server supports ``X-Sendfile``,
    ``use_x_sendfile=True`` will tell the server to send the given path, which
    is much more efficient than reading it in Python.

    :param path_or_file: The path to the file to send, relative to the current
        directory if a relative path is given. Alternatively, a file-like object
        in ``rb`` mode. The path will be ``file.name`` if available.
    :param environ: The WSGI environ for the current request.
    :param mimetype: The MIME type to send for the file. If not provided, it is
        detected from the file, and falls back to ``application/octet-stream``.
    :param as_attachment: Indicate to a browser that it should offer to save the
        file instead of displaying it.
    :param download_name: The default name browsers will use when saving the
        file. Defaults to the passed file name.
    :param conditional: Enable conditional and range responses based on request
        headers.
    :param etag: Generate a strong ETag based on the file's last modified time
        and size if available. Or an already generated ETag, assumed strong if a
        ``str`` is given.
    :param last_modified: The last modified time as a ``datetime`` or seconds
        seconds. If not provided, it is detected from the file. Typically only
        needs to be provided for ``BytesIO``.
    :param max_age: How long the client should cache the file, in seconds. If
        set, ``Cache-Control`` will be ``public``, otherwise it will be
        ``no-cache`` to prefer conditional caching.
    :param use_x_sendfile: Set the ``X-Sendfile`` header to let the server
        efficiently send the file. Requires support from the HTTP server..
    :param response_class: Build the response using this class. Defaults to
        :class:`.Response`.
    :param _root_path: Do not use. For internal use only. Use
        :func:`send_from_directory` to safely send files under a path.

    .. versionchanged:: 3.2
        Improve handling of conditional and range requests.

        Path, size, and modification time are detected from file-like objects.
        The position is set to the beginning.

        If ``mimetype`` nor ``download_name`` is given, default to
        ``application/octet-stream``.

    .. versionchanged:: 2.0.2
        ``send_file`` only sets a detected ``Content-Encoding`` if
        ``as_attachment`` is disabled.

    .. versionadded:: 2.0
        Adapted from Flask's implementation.

        ``download_name`` replaces Flask's ``attachment_filename`` parameter. If
        ``as_attachment=False``, it is passed with
        ``Content-Disposition: inline`` instead.

        ``max_age`` replaces Flask's ``cache_timeout`` parameter.
        ``conditional`` is enabled and ``max_age`` is not set by default.

        ``etag`` replaces Flask's ``add_etags`` parameter. It can be a string to
        use instead of generating one.

        If an encoding is returned when guessing ``mimetype``, set the
        ``Content-Encoding`` header.
    """
    if response_class is None:
        from .wrappers import Response

        response_class = Response

    path: os.PathLike[str] | str | None = None
    file: t.IO[bytes]
    size: int | None = None
    headers = Headers()

    if isinstance(path_or_file, (os.PathLike, str)):
        path = path_or_file

        # Flask will pass app.root_path, allowing its send_file wrapper
        # to not have to deal with paths.
        if _root_path is not None:
            path = os.path.join(_root_path, path)
        else:
            path = os.path.abspath(path)

        stat = os.stat(path)
        size = stat.st_size

        if last_modified is None:
            last_modified = stat.st_mtime

        file = open(path, "rb")
    else:
        file = path_or_file

        if isinstance(file, io.TextIOBase):
            raise ValueError("File must be in binary mode, or 'BytesIO'.")

        if hasattr(file, "name"):
            path = file.name

        if file.seekable():
            size = file.seek(0, os.SEEK_END)
            file.seek(0)

        if size is None or last_modified is None:
            try:
                fileno = file.fileno()
            except OSError:
                pass
            else:
                stat = os.stat(fileno)

                if size is None:
                    size = stat.st_size

                if last_modified is None:
                    last_modified = stat.st_mtime

    if download_name is None and path is not None:
        download_name = os.path.basename(path)

    if mimetype is None:
        if download_name is None:
            mimetype = "application/octet-stream"
        else:
            mimetype, encoding = mimetypes.guess_type(download_name)

            if mimetype is None:
                mimetype = "application/octet-stream"

            # Don't send encoding for attachments, it causes browsers to
            # decompress tar.gz files when saving.
            if encoding is not None and not as_attachment:
                headers["Content-Encoding"] = encoding

    if download_name is not None:
        if download_name.isascii():
            names = {"filename": download_name}
        else:
            simple = unicodedata.normalize("NFKD", download_name)
            simple = simple.encode("ascii", "ignore").decode("ascii")
            # safe = RFC 5987 attr-char
            quoted = quote(download_name, safe="!#$&+-.^_`|~")
            names = {"filename": simple, "filename*": f"UTF-8''{quoted}"}

        value = "attachment" if as_attachment else "inline"
        headers.set("Content-Disposition", value, **names)
    elif as_attachment:
        raise TypeError(
            "No name provided for attachment. Either pass 'download_name', or"
            " pass a path instead of a file."
        )

    rv = response_class(
        wrap_file(environ, file),
        mimetype=mimetype,
        headers=headers,
        direct_passthrough=True,
    )
    # Always call file.close, wsgi.file_wrapper does not require a close method.
    rv.call_on_close(file.close)

    if use_x_sendfile and path is not None:
        rv.headers["X-Sendfile"] = path
        rv.response = []

    if size is not None:
        rv.content_length = size

    if last_modified is not None:
        rv.last_modified = last_modified

    cache_control = ResponseCacheControl()
    cache_control.no_cache = True

    # Flask will pass app.get_send_file_max_age, allowing its send_file
    # wrapper to not have to deal with paths.
    if callable(max_age):
        max_age = max_age(path)

    if max_age is not None:
        if max_age > 0:
            cache_control.no_cache = None
            cache_control.public = True

        cache_control.max_age = max_age
        rv.expires = int(time() + max_age)

    rv.cache_control = cache_control

    if isinstance(etag, str):
        rv.etag = etag
    elif etag:
        parts = []

        if last_modified is not None:
            if isinstance(last_modified, datetime):
                parts.append(str(last_modified.timestamp()))
            else:
                parts.append(str(last_modified))

        if size is not None:
            parts.append(str(size))

        rv.etag = "-".join(parts)

    if conditional:
        from .wrappers.request import Request

        request = Request(environ)

        try:
            rv.apply_conditions(request)
            rv.apply_range(request)
        except HTTPException:
            rv.close()
            raise

        if rv.status_code == 304:
            rv.headers.pop("X-Sendfile", None)

    return rv


def send_from_directory(
    directory: os.PathLike[str] | str,
    path: os.PathLike[str] | str,
    environ: WSGIEnvironment,
    **kwargs: t.Any,
) -> Response:
    """Send a file from within a directory using :func:`send_file`.

    This is a secure way to serve files from a folder, such as static
    files or uploads. Uses :func:`~werkzeug.security.safe_join` to
    ensure the path coming from the client is not maliciously crafted to
    point outside the specified directory.

    If the final path does not point to an existing regular file,
    returns a 404 :exc:`~werkzeug.exceptions.NotFound` error.

    :param directory: The directory that ``path`` must be located under. This *must not*
        be a value provided by the client, otherwise it becomes insecure.
    :param path: The path to the file to send, relative to ``directory``. This is the
        part of the path provided by the client, which is checked for security.
    :param environ: The WSGI environ for the current request.
    :param kwargs: Arguments to pass to :func:`send_file`.

    .. versionadded:: 2.0
        Adapted from Flask's implementation.
    """
    path_str = safe_join(os.fspath(directory), os.fspath(path))

    if path_str is None:
        raise NotFound()

    # Flask will pass app.root_path, allowing its send_from_directory
    # wrapper to not have to deal with paths.
    if "_root_path" in kwargs:
        path_str = os.path.join(kwargs["_root_path"], path_str)

    if not os.path.isfile(path_str):
        raise NotFound()

    return send_file(path_str, environ, **kwargs)


def import_string(import_name: str, silent: bool = False) -> t.Any:
    """Imports an object based on a string.  This is useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).

    If `silent` is True the return value will be `None` if the import fails.

    :param import_name: the dotted name for the object to import.
    :param silent: if set to `True` import errors are ignored and
                   `None` is returned instead.
    :return: imported object
    """
    import_name = import_name.replace(":", ".")
    try:
        try:
            __import__(import_name)
        except ImportError:
            if "." not in import_name:
                raise
        else:
            return sys.modules[import_name]

        module_name, obj_name = import_name.rsplit(".", 1)
        module = __import__(module_name, globals(), locals(), [obj_name])
        try:
            return getattr(module, obj_name)
        except AttributeError as e:
            raise ImportError(e) from None

    except ImportError as e:
        if not silent:
            raise ImportStringError(import_name, e).with_traceback(
                sys.exc_info()[2]
            ) from None

    return None


def find_modules(
    import_path: str, include_packages: bool = False, recursive: bool = False
) -> t.Iterator[str]:
    """Finds all the modules below a package.  This can be useful to
    automatically import all views / controllers so that their metaclasses /
    function decorators have a chance to register themselves on the
    application.

    Packages are not returned unless `include_packages` is `True`.  This can
    also recursively list modules but in that case it will import all the
    packages to get the correct load path of that module.

    :param import_path: the dotted name for the package to find child modules.
    :param include_packages: set to `True` if packages should be returned, too.
    :param recursive: set to `True` if recursion should happen.
    :return: generator
    """
    module = import_string(import_path)
    path = getattr(module, "__path__", None)
    if path is None:
        raise ValueError(f"{import_path!r} is not a package")
    basename = f"{module.__name__}."
    for _importer, modname, ispkg in pkgutil.iter_modules(path):
        modname = basename + modname
        if ispkg:
            if include_packages:
                yield modname
            if recursive:
                yield from find_modules(modname, include_packages, True)
        else:
            yield modname


class ImportStringError(ImportError):
    """Provides information about a failed :func:`import_string` attempt."""

    #: String in dotted notation that failed to be imported.
    import_name: str
    #: Wrapped exception.
    exception: BaseException

    def __init__(self, import_name: str, exception: BaseException) -> None:
        self.import_name = import_name
        self.exception = exception
        msg = import_name
        name = ""
        tracked = []
        for part in import_name.replace(":", ".").split("."):
            name = f"{name}.{part}" if name else part
            imported = import_string(name, silent=True)
            if imported:
                tracked.append((name, getattr(imported, "__file__", None)))
            else:
                track = [f"- {n!r} found in {i!r}." for n, i in tracked]
                track.append(f"- {name!r} not found.")
                track_str = "\n".join(track)
                msg = (
                    f"import_string() failed for {import_name!r}. Possible reasons"
                    f" are:\n\n"
                    "- missing __init__.py in a package;\n"
                    "- package or module path not included in sys.path;\n"
                    "- duplicated package or module name taking precedence in"
                    " sys.path;\n"
                    "- missing module, class, function or variable;\n\n"
                    f"Debugged import:\n\n{track_str}\n\n"
                    f"Original exception:\n\n{type(exception).__name__}: {exception}"
                )
                break

        super().__init__(msg)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}({self.import_name!r}, {self.exception!r})>"


if not t.TYPE_CHECKING:

    def __getattr__(name: str) -> t.Any:
        import warnings

        if name == "environ_property":
            from ._header_property import environ_property

            warnings.warn(
                "'environ_property' is deprecated and will be removed in"
                " Werkzeug 4.0. Access 'environ' directly instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return environ_property

        if name == "header_property":
            from ._header_property import header_property

            warnings.warn(
                "'header_property' is deprecated and will be removed in"
                " Werkzeug 4.0. Access 'headers' directly instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return header_property

        raise AttributeError(name)
