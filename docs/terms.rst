===============
Important Terms
===============

.. currentmodule:: werkzeug

This page covers important terms used in the documentation and Werkzeug
itself.


WSGI
----

WSGI a specification for Python web applications Werkzeug follows.  It was
specified in the :pep:`3333` and is widely supported.  Unlike previous solutions
it guarantees that web applications, servers and utilities can work together.

Response Object
---------------

For Werkzeug, a response object is an object that works like a WSGI
application but does not do any request processing.  Usually you have a view
function or controller method that processes the request and assembles a
response object.

A response object is *not* necessarily the :class:`Response` class or a
subclass thereof.

For example Pylons/webob provide a very similar response class that can
be used as well (:class:`webob.Response`).

View Function
-------------

Often people speak of MVC (Model, View, Controller) when developing web
applications.  However, the Django framework coined MTV (Model, Template,
View) which basically means the same but reduces the concept to the data
model, a function that processes data from the request and the database and
renders a template.

Werkzeug itself does not tell you how you should develop applications, but the
documentation often speaks of view functions that work roughly the same.  The
idea of a view function is that it's called with a request object (and
optionally some parameters from an URL rule) and returns a response object.
