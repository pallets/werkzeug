from __future__ import annotations

import datetime as dt
import logging
import re
import typing as t

T = t.TypeVar("T")
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
            _logger.addHandler(logging.StreamHandler())

    getattr(_logger, type)(message.rstrip(), *args, **kwargs)


@t.overload
def _dt_as_utc(value: None) -> None: ...
@t.overload
def _dt_as_utc(value: dt.datetime) -> dt.datetime: ...
def _dt_as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    elif value.tzinfo != dt.UTC:
        return value.astimezone(dt.UTC)

    return value


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
