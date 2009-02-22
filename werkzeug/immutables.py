# -*- coding: utf-8 -*-
"""
    werkzeug.immutables
    ~~~~~~~~~~~~~~~~~~~

    This module provides mixins and classes with an immutable interface.

    :copyright: Copyright 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug._internal import _proxy_repr


def is_immutable(self):
    raise TypeError('%r objects are immutable' % self.__class__.__name__)


class ImmutableListMixin(object):
    """Makes a :class:`list` immutable."""

    def __delitem__(self, key):
        is_immutable(self)

    def __delslice__(self, i, j):
        is_immutable(self)

    def __iadd__(self, other):
        is_immutable(self)
    __imul__ = __iadd__

    def __setitem__(self, key, value):
        is_immutable(self)

    def __setslice__(self, i, j, value):
        is_immutable(self)

    def append(self, item):
        is_immutable(self)
    remove = append

    def extend(self, iterable):
        is_immutable(self)

    def insert(self, pos, value):
        is_immutable(self)

    def pop(self, index=-1):
        is_immutable(self)

    def reverse(self):
        is_immutable(self)

    def sort(self, cmp=None, key=None, reverse=None):
        is_immutable(self)


class ImmutableList(ImmutableListMixin, list):
    """An immutable class:`list`."""

    __repr__ = _proxy_repr(list)


class ImmutableDictMixin(object):
    """Makes a :class:`dict` immutable."""

    def setdefault(self, key, default=None):
        is_immutable(self)

    def update(self, *args, **kwargs):
        is_immutable(self)

    def pop(self, key, default=None):
        is_immutable(self)

    def popitem(self):
        is_immutable(self)

    def __setitem__(self, key, value):
        is_immutable(self)

    def __delitem__(self, key):
        is_immutable(self)

    def clear(self):
        is_immutable(self)


class ImmutableDict(ImmutableDictMixin, dict):
    """An immutable :class:`dict`."""

    __repr__ = _proxy_repr(dict)


class ImmutableMultiDictMixin(ImmutableDictMixin):
    """Makes a :class:`MultiDict` immutable."""

    def popitemlist(self):
        is_immutable(self)

    def poplist(self, key):
        is_immutable(self)

    def setlist(self, key, new_list):
        is_immutable(self)

    def setlistdefault(self, key, default_list=None):
        is_immutable(self)


# right before the CombinedMultiDict the ImmutableMultiDictMixin is
# imported.  So make sure not to move the class around in that file!
# At exactly this position the MultiDict is safely importable.
from werkzeug.utils import MultiDict


class ImmutableMultiDict(ImmutableMultiDictMixin, MultiDict):
    """An immutable :class:`MultiDict`."""
