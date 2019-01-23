=============
Secure Cookie
=============

.. warning::
    .. deprecated:: 0.15
        This will be removed in version 1.0. It has moved to
        https://github.com/pallets/secure-cookie.

.. automodule:: werkzeug.contrib.securecookie

Security
========

The default implementation uses Pickle as this is the only module that
used to be available in the standard library when this module was created.
If you have simplejson available it's strongly recommended to create a
subclass and replace the serialization method::

    import json
    from werkzeug.contrib.securecookie import SecureCookie

    class JSONSecureCookie(SecureCookie):
        serialization_method = json

The weakness of Pickle is that if someone gains access to the secret key
the attacker can not only modify the session but also execute arbitrary
code on the server.


Reference
=========

.. autoclass:: SecureCookie
   :members:

   .. attribute:: new

      `True` if the cookie was newly created, otherwise `False`

   .. attribute:: modified

      Whenever an item on the cookie is set, this attribute is set to `True`.
      However this does not track modifications inside mutable objects
      in the cookie:

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


.. autoexception:: UnquoteError
