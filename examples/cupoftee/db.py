# -*- coding: utf-8 -*-
"""
    cupoftee.db
    ~~~~~~~~~~~

    A simple object database.  As long as the server is not running in
    multiprocess mode that's good enough.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from pickle import dumps
from pickle import loads
from threading import Lock

try:
    import dbm
except ImportError:
    import anydbm as dbm


class Database(object):
    def __init__(self, filename):
        self.filename = filename
        self._fs = dbm.open(filename, "cf")
        self._local = {}
        self._lock = Lock()

    def __getitem__(self, key):
        with self._lock:
            return self._load_key(key)

    def _load_key(self, key):
        if key in self._local:
            return self._local[key]
        rv = loads(self._fs[key])
        self._local[key] = rv
        return rv

    def __setitem__(self, key, value):
        self._local[key] = value

    def __delitem__(self, key, value):
        with self._lock:
            self._local.pop(key, None)
            if key in self._fs:
                del self._fs[key]

    def __del__(self):
        self.close()

    def __contains__(self, key):
        with self._lock:
            try:
                self._load_key(key)
            except KeyError:
                pass
            return key in self._local

    def setdefault(self, key, factory):
        with self._lock:
            try:
                rv = self._load_key(key)
            except KeyError:
                self._local[key] = rv = factory()
            return rv

    def sync(self):
        with self._lock:
            for key, value in self._local.items():
                self._fs[key] = dumps(value, 2)
            self._fs.sync()

    def close(self):
        try:
            self.sync()
            self._fs.close()
        except Exception:
            pass
