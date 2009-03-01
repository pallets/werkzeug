========
Sessions
========

.. automodule:: werkzeug.contrib.sessions

.. autoclass:: Session

   .. attribute:: sid
    
      The session ID as string.

   .. attribute:: new

      `True` is the cookie was newly created, otherwise `False`

   .. attribute:: modified

      Whenever an item on the cookie is set this is set to `True`.  However
      this does not track modifications inside mutable objects in the cookie:

      >>> c = SecureCookie()
      >>> c["foo"] = [1, 2, 3]
      >>> c.modified
      True
      >>> c.modified = False
      >>> c["foo"].append(4)
      >>> c.modified
      False

      In that situation it has to be set to `modified` by hand so that
      :attr:`should_save` can pick it up.

   .. autoattribute:: should_save

.. autoclass:: SessionStore
   :members:

.. autoclass:: FilesystemSessionStore

.. autoclass:: SessionMiddleware
