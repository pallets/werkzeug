from __future__ import annotations

import logging
import re
import sys
import typing as t
from datetime import datetime
from datetime import timezone

if t.TYPE_CHECKING:
    from _typeshed.wsgi import WSGIEnvironment

    from .wrappers.request import Request

_logger: logging.Logger | None = None


class _Missing:
    def __repr__(self) -> str:
        return "no value"

    def __reduce__(self) -> str:
        return "_missing"


_missing = _Missing()


def _wsgi_decoding_dance(s: str) -> str:
    return s.encode("latin1").decode(errors="replace")


def _wsgi_encoding_dance(s: str) -> str:
    return s.encode().decode("latin1")


def _get_environ(obj: WSGIEnvironment | Request) -> WSGIEnvironment:
    env = getattr(obj, "environ", obj)
    assert isinstance(env, dict), (
        f"{type(obj).__name__!r} is not a WSGI environment (has to be a dict)"
    )
    return env


def _has_level_handler(logger: logging.Logger) -> bool:
    """Check if there is a handler in the logging chain that will handle
    the given logger's effective level.
    """
    level = logger.getEffectiveLevel()
    current: logging.Logger | None = logger

    while current:
        if any(handler.level <= level for handler in current.handlers):
            return True

        if not current.propagate:
            break

        current = current.parent

    return False


class _ColorStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """On Windows, wrap stream with Colorama for ANSI style support."""

    def __init__(self) -> None:
        try:
            import colorama
        except ImportError:
            stream = None
        else:
            stream = colorama.AnsiToWin32(sys.stderr)

        super().__init__(stream)


def _log(type: str, message: str, *args: t.Any, **kwargs: t.Any) -> None:
    """Log a message to the 'werkzeug' logger.

    The logger is created the first time it is needed. If there is no
    level set, it is set to :data:`logging.INFO`. If there is no handler
    for the logger's effective level, a :class:`logging.StreamHandler`
    is added.
    """
    global _logger

    if _logger is None:
        _logger = logging.getLogger("werkzeug")

        if _logger.level == logging.NOTSET:
            _logger.setLevel(logging.INFO)

        if not _has_level_handler(_logger):
            _logger.addHandler(_ColorStreamHandler())

    getattr(_logger, type)(message.rstrip(), *args, **kwargs)


@t.overload
def _dt_as_utc(dt: None) -> None: ...


@t.overload
def _dt_as_utc(dt: datetime) -> datetime: ...


def _dt_as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return dt

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        return dt.astimezone(timezone.utc)

    return dt


_plain_int_re = {
    10: re.compile(r"-?[0-9]+", re.ASCII),
    16: re.compile(r"-?[0-9a-f]+", re.ASCII | re.IGNORECASE),
}


def _plain_int(value: str, base: t.Literal[10, 16] = 10) -> int:
    """Parse an int only if it valid ASCII characters for the base.

    This disallows ``+``, ``_``, ``0x``, and non-ASCII digits, which are
    accepted by ``int`` but are not allowed in HTTP header values.

    Any surrounding spaces and tabs are stripped.
    """
    value = value.strip(" \t")

    if _plain_int_re[base].fullmatch(value) is None:
        raise ValueError(value)

    return int(value, base)
