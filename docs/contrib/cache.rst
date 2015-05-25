=====
Cache
=====

.. automodule:: werkzeug.contrib.cache


Cache System API
================

.. autoclass:: BaseCache
   :members:


Cache Systems
=============

.. autoclass:: NullCache

.. autoclass:: SimpleCache

.. autoclass:: MemcachedCache

.. class:: GAEMemcachedCache

   This class is deprecated in favour of :class:`MemcachedCache` which
   now supports Google Appengine as well.

   .. versionchanged:: 0.8
      Deprecated in favour of :class:`MemcachedCache`.

.. autoclass:: RedisCache

.. autoclass:: FileSystemCache

.. autoclass:: UWSGICache
