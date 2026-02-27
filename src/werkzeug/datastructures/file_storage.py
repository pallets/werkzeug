from __future__ import annotations

import collections.abc as cabc
import mimetypes
import os
import typing as t
from io import BytesIO
from os import fsdecode
from os import fspath

from .._internal import _plain_int
from ..http import parse_options_header
from .headers import Headers
from .structures import MultiDict


class FileStorage:
    """The :class:`FileStorage` class is a thin wrapper over incoming files.
    It is used by the request object to represent uploaded files.  All the
    attributes of the wrapper stream are proxied by the file storage so
    it's possible to do ``storage.read()`` instead of the long form
    ``storage.stream.read()``.
    """

    def __init__(
        self,
        stream: t.IO[bytes] | None = None,
        filename: str | None = None,
        name: str | None = None,
        content_type: str | None = None,
        content_length: int | None = None,
        headers: Headers | None = None,
    ):
        self.name = name
        self.stream = stream or BytesIO()
        self.filename = _guess_filename(self.stream, filename)

        if headers is None:
            headers = Headers()
        self.headers = headers
        if content_type is not None:
            headers["Content-Type"] = content_type
        if content_length is not None:
            headers["Content-Length"] = str(content_length)

    def _parse_content_type(self) -> None:
        if not hasattr(self, "_parsed_content_type"):
            self._parsed_content_type = parse_options_header(self.content_type)

    @property
    def content_type(self) -> str | None:
        """The content-type sent in the header.  Usually not available"""
        return self.headers.get("content-type")

    @property
    def content_length(self) -> int:
        """The content-length sent in the header.  Usually not available"""
        if "content-length" in self.headers:
            try:
                return _plain_int(self.headers["content-length"])
            except ValueError:
                pass

        return 0

    @property
    def mimetype(self) -> str:
        """Like :attr:`content_type`, but without parameters (eg, without
        charset, type etc.) and always lowercase.  For example if the content
        type is ``text/HTML; charset=utf-8`` the mimetype would be
        ``'text/html'``.

        .. versionadded:: 0.7
        """
        self._parse_content_type()
        return self._parsed_content_type[0].lower()

    @property
    def mimetype_params(self) -> dict[str, str]:
        """The mimetype parameters as dict.  For example if the content
        type is ``text/html; charset=utf-8`` the params would be
        ``{'charset': 'utf-8'}``.

        .. versionadded:: 0.7
        """
        self._parse_content_type()
        return self._parsed_content_type[1]

    def save(
        self, dst: str | os.PathLike[str] | t.IO[bytes], buffer_size: int = 16384
    ) -> None:
        """Save the file to a destination path or file object.  If the
        destination is a file object you have to close it yourself after the
        call.  The buffer size is the number of bytes held in memory during
        the copy process.  It defaults to 16KB.

        For secure file saving also have a look at :func:`secure_filename`.

        :param dst: a filename, :class:`os.PathLike`, or open file
            object to write to.
        :param buffer_size: Passed as the ``length`` parameter of
            :func:`shutil.copyfileobj`.

        .. versionchanged:: 1.0
            Supports :mod:`pathlib`.
        """
        from shutil import copyfileobj

        close_dst = False

        if hasattr(dst, "__fspath__"):
            dst = fspath(dst)

        if isinstance(dst, str):
            dst = open(dst, "wb")
            close_dst = True

        try:
            copyfileobj(self.stream, dst, buffer_size)
        finally:
            if close_dst:
                dst.close()

    def close(self) -> None:
        """Close the underlying file if possible."""
        try:
            self.stream.close()
        except Exception:
            pass

    def __bool__(self) -> bool:
        return bool(self.filename)

    def __getattr__(self, name: str) -> t.Any:
        try:
            return getattr(self.stream, name)
        except AttributeError:
            # SpooledTemporaryFile on Python < 3.11 doesn't implement IOBase,
            # get the attribute from its backing file instead.
            if hasattr(self.stream, "_file"):
                return getattr(self.stream._file, name)
            raise

    def __iter__(self) -> cabc.Iterator[bytes]:
        return iter(self.stream)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self.filename!r} ({self.content_type!r})>"


class FileMultiDict(MultiDict[str, FileStorage]):
    """A :class:`MultiDict` for managing form data file values. Used by
    :class:`.EnvironBuilder` for tests.

    .. versionadded:: 0.5
    """

    def add_file(
        self,
        name: str,
        file: str | os.PathLike[str] | t.IO[bytes] | FileStorage,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> None:
        """Add a file to the given key. Can be passed a filename or IO object,
        which will construct a :class:`.FileStorage` object.

        :param name: The key to add the file to.
        :param file: The file to add. Constructs a :class:`FileStorage` object
            if the value is not one.
        :param filename: The filename to set for the field. Defaults to ``file``
            if it's a filename or ``file.name`` if it's an IO object.
        :param content_type: The content type to set for the field. Defaults to
            guessing based on the filename, falling back to
            ``application/octet-stream``.

        .. versionchanged:: 3.2
            The filename is detected from an IO object.
        """
        if isinstance(file, FileStorage):
            self.add(name, file)
            return

        if isinstance(file, (str, os.PathLike)):
            if filename is None:
                filename = os.fspath(file)

            file_obj: t.IO[bytes] = open(file, "rb")
        else:
            file_obj = file  # type: ignore[assignment]
            filename = _guess_filename(file_obj, filename)

        if filename is not None and content_type is None:
            content_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )

        self.add(name, FileStorage(file_obj, filename, name, content_type))

    def close(self) -> None:
        """Call :meth:`~FileStorage.close` on every open file.

        .. versionadded:: 3.2
        """
        for values in self.listvalues():
            for value in values:
                if not value.closed:
                    value.close()

    def clear(self) -> None:
        """Call :meth:`close`, then remove all items.

        .. versionadded:: 3.2
        """
        self.close()
        super().clear()


def _guess_filename(stream: t.IO[t.Any], filename: str | None) -> str | None:
    if filename is not None:
        return fsdecode(filename)

    filename = getattr(stream, "name", None)

    if filename is not None:
        filename = fsdecode(filename)

        # Python names special streams like `<stderr>`, ignore these.
        if filename[:1] == "<" and filename[-1:] == ">":
            filename = None

    return filename
