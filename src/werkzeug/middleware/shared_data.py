"""
Serve Shared Static Files
=========================

.. autoclass:: SharedDataMiddleware
    :members: is_allowed
"""

from __future__ import annotations

import collections.abc as cabc
import datetime as dt
import importlib.util
import os
import posixpath
import typing as t
from fnmatch import fnmatch
from io import BytesIO

from ..security import safe_join
from ..utils import send_file
from ..wrappers import Request

_TOpener = t.Callable[[], tuple[t.IO[bytes], dt.datetime, int]]
_TLoader = t.Callable[[str | None], tuple[str | None, _TOpener | None]]

if t.TYPE_CHECKING:
    from _typeshed.wsgi import WSGIApplication


class SharedDataMiddleware:
    """Serve static files during development. Use the HTTP server in front of
    the application to serve static files in production.

    Given a map of base URL paths to directories, this will match a requested
    file under a path to a file in a directory. Unmatched paths will be
    forwarded to the wrapped application.

    - ``"/static": "static"`` matches paths under the "static" directory.
    - ``"/robots.txt": "generated/robots.txt"`` matches a single path and file.
    - ``"/toolbar": ("toolbar", "static")`` matches paths under the "static"
      directory within the importable "toolbar" Python package.

    :param app: The application to use for paths not handled by the middleware.
        Using :exc:`.NotFound` will return 404 for any other path.
    :param exports: Map URL paths to a folder with static files. A ``str`` is a
        filesystem path to a directory or single file, relative to the current
        directory. A ``(package, path)`` tuple is a path within an importable
        Python package. URL path keys are matched in order.
    :param disallow: A pattern for :func:`~fnmatch.fnmatch`. If it matches the
        loaded filename, the file is not served.
    :param cache_timeout: Set the ``Cache-Control`` ``max-age`` directive. If
        not set, conditional caching is used, which is typically what you want.

    .. versionchanged:: 3.2
        The ``cache`` and ``fallback_mimetype`` parameters are deprecated and
        will be removed in Werkzeug 4.0.

        The ``cache_timeout`` parameter is disabled by default, enabling
        conditional caching.

        Conditional and range requests are supported.

    .. versionchanged:: 1.0
        The default ``fallback_mimetype`` is ``application/octet-stream``
        If a filename looks like a text mimetype, the ``utf-8`` charset
        is added to it.

    .. versionadded:: 0.6
        Added ``fallback_mimetype``.

    .. versionchanged:: 0.5
        Added ``cache_timeout``.
    """

    def __init__(
        self,
        app: WSGIApplication,
        exports: (
            cabc.Mapping[str, str | tuple[str, str]]
            | t.Iterable[tuple[str, str | tuple[str, str]]]
        ),
        disallow: str | None = None,
        cache: None = None,
        cache_timeout: int | None = None,
        fallback_mimetype: None = None,
    ) -> None:
        self.app = app
        self.exports: list[tuple[str, _TLoader]] = []
        self.cache = cache
        self.cache_timeout = cache_timeout
        self.fallback_mimetype = fallback_mimetype

        if cache is not None:
            import warnings

            warnings.warn(
                "The 'cache' parameter is deprecated and will be removed"
                " in Werkzeug 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        if fallback_mimetype is not None:
            import warnings

            warnings.warn(
                "The 'fallback_mimetype' parameter is deprecated and will be"
                " removed in Werkzeug 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        if isinstance(exports, cabc.Mapping):
            exports = exports.items()

        for key, value in exports:
            if isinstance(value, tuple):
                loader = self.get_package_loader(*value)
            elif isinstance(value, str):
                if os.path.isfile(value):
                    loader = self.get_file_loader(value)
                else:
                    loader = self.get_directory_loader(value)
            else:
                raise TypeError(f"unknown def {value!r}")

            self.exports.append((key, loader))

        if disallow is not None:
            self.is_allowed = lambda x: x is not None and not fnmatch(x, disallow)  # type: ignore[method-assign,assignment]

    def is_allowed(self, filename: str | None) -> bool:
        """Subclasses can override this method to disallow the access to
        certain files.  However by providing `disallow` in the constructor
        this method is overwritten.
        """
        return True

    def _opener(self, filename: str) -> _TOpener:
        return lambda: (
            open(filename, "rb"),
            dt.datetime.fromtimestamp(os.path.getmtime(filename), tz=dt.UTC),
            os.path.getsize(filename),
        )

    def get_file_loader(self, filename: str) -> _TLoader:
        return lambda x: (os.path.basename(filename), self._opener(filename))

    def get_package_loader(self, package: str, package_path: str) -> _TLoader:
        load_time = dt.datetime.now(dt.UTC)
        spec = importlib.util.find_spec(package)
        reader = spec.loader.get_resource_reader(package)  # type: ignore[union-attr]

        def loader(
            path: str | None,
        ) -> tuple[str | None, _TOpener | None]:
            if path is None:
                return None, None

            path = safe_join(package_path, path)

            if path is None:
                return None, None

            basename = posixpath.basename(path)

            try:
                resource = reader.open_resource(path)
            except OSError:
                return None, None

            if isinstance(resource, BytesIO):
                return (
                    basename,
                    lambda: (resource, load_time, len(resource.getvalue())),
                )

            return (
                basename,
                lambda: (
                    resource,
                    dt.datetime.fromtimestamp(
                        os.path.getmtime(resource.name), tz=dt.UTC
                    ),
                    os.path.getsize(resource.name),
                ),
            )

        return loader

    def get_directory_loader(self, directory: str) -> _TLoader:
        def loader(
            path: str | None,
        ) -> tuple[str | None, _TOpener | None]:
            if path is not None:
                path = safe_join(directory, path)

                if path is None:
                    return None, None
            else:
                path = directory

            if os.path.isfile(path):
                return os.path.basename(path), self._opener(path)

            return None, None

        return loader

    @Request.application
    def __call__(self, request: Request) -> WSGIApplication:
        path = request.path

        for search_path, loader in self.exports:
            if search_path == path:
                filename, opener = loader(None)

                if opener is not None:
                    break

            if not search_path.endswith("/"):
                search_path += "/"

            if path.startswith(search_path):
                filename, opener = loader(path[len(search_path) :])

                if opener is not None:
                    break
        else:
            return self.app

        if not self.is_allowed(filename):
            return self.app

        f, mtime, size = opener()
        response = send_file(
            f,
            request.environ,
            download_name=filename,
            conditional=bool(self.cache),
            last_modified=mtime,
            max_age=self.cache_timeout,
        )

        if response.content_length is None:
            response.content_length = size

        if (
            self.fallback_mimetype is not None
            and response.mimetype == "application/octet-stream"
        ):
            response.mimetype = self.fallback_mimetype

        return response
