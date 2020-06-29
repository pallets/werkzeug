from __future__ import annotations

import datetime
import json
import uuid

from ..exceptions import BadRequest
from typing import Dict, List, Union


class _JSONModule:
    @staticmethod
    def _default(o):
        if isinstance(o, datetime.date):
            return o.isoformat()

        if isinstance(o, uuid.UUID):
            return str(o)

        if hasattr(o, "__html__"):
            return str(o.__html__())

        raise TypeError()

    @classmethod
    def dumps(cls, obj, **kw):
        kw.setdefault("separators", (",", ":"))
        kw.setdefault("default", cls._default)
        kw.setdefault("sort_keys", True)
        return json.dumps(obj, **kw)

    @staticmethod
    def loads(s: bytes, **kw) -> Union[List[int], Dict[str, str]]:
        return json.loads(s, **kw)


class JSONMixin:
    """Mixin to parse :attr:`data` as JSON. Can be mixed in for both
    :class:`~werkzeug.wrappers.Request` and
    :class:`~werkzeug.wrappers.Response` classes.
    """

    #: A module or other object that has ``dumps`` and ``loads``
    #: functions that match the API of the built-in :mod:`json` module.
    json_module = _JSONModule

    @property
    def json(self):
        """The parsed JSON data if :attr:`mimetype` indicates JSON
        (:mimetype:`application/json`, see :meth:`is_json`).

        Calls :meth:`get_json` with default arguments.
        """
        return self.get_json()

    @property
    def is_json(self):
        """Check if the mimetype indicates JSON data, either
        :mimetype:`application/json` or :mimetype:`application/*+json`.
        """
        mt = self.mimetype
        return (
            mt == "application/json"
            or mt.startswith("application/")
            and mt.endswith("+json")
        )

    def _get_data_for_json(self, cache):
        try:
            return self.get_data(cache=cache)
        except TypeError:
            # Response doesn't have cache param.
            return self.get_data()

    # Cached values for ``(silent=False, silent=True)``. Initialized
    # with sentinel values.
    _cached_json = (Ellipsis, Ellipsis)

    def get_json(self, force=False, silent=False, cache=True):
        """Parse :attr:`data` as JSON.

        If the mimetype does not indicate JSON
        (:mimetype:`application/json`, see :meth:`is_json`), this
        returns ``None``.

        If parsing fails, :meth:`on_json_loading_failed` is called and
        its return value is used as the return value.

        :param force: Ignore the mimetype and always try to parse JSON.
        :param silent: Silence parsing errors and return ``None``
            instead.
        :param cache: Store the parsed JSON to return for subsequent
            calls.
        """
        if cache and self._cached_json[silent] is not Ellipsis:
            return self._cached_json[silent]

        if not (force or self.is_json):
            return None

        data = self._get_data_for_json(cache=cache)

        try:
            rv = self.json_module.loads(data)
        except ValueError as e:
            if silent:
                rv = None

                if cache:
                    normal_rv, _ = self._cached_json
                    self._cached_json = (normal_rv, rv)
            else:
                rv = self.on_json_loading_failed(e)

                if cache:
                    _, silent_rv = self._cached_json
                    self._cached_json = (rv, silent_rv)
        else:
            if cache:
                self._cached_json = (rv, rv)

        return rv

    def on_json_loading_failed(self, e):
        """Called if :meth:`get_json` parsing fails and isn't silenced.
        If this method returns a value, it is used as the return value
        for :meth:`get_json`. The default implementation raises
        :exc:`~werkzeug.exceptions.BadRequest`.
        """
        raise BadRequest(f"Failed to decode JSON object: {e}")
