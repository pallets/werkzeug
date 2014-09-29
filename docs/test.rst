==============
Test Utilities
==============

.. module:: werkzeug.test

Quite often you want to unittest your application or just check the output
from an interactive python session.  In theory that is pretty simple because
you can fake a WSGI environment and call the application with a dummy
`start_response` and iterate over the application iterator but there are
argumentably better ways to interact with an application.


Diving In
=========

Werkzeug provides a `Client` object which you can pass a WSGI application (and
optionally a response wrapper) which you can use to send virtual requests to
the application.

A response wrapper is a callable that takes three arguments: the application
iterator, the status and finally a list of headers.  The default response
wrapper returns a tuple.  Because response objects have the same signature,
you can use them as response wrapper, ideally by subclassing them and hooking
in test functionality.

>>> from werkzeug.test import Client
>>> from werkzeug.testapp import test_app
>>> from werkzeug.wrappers import BaseResponse
>>> c = Client(test_app, BaseResponse)
>>> resp = c.get('/')
>>> resp.status_code
200
>>> resp.headers
Headers([('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', '8339')])
>>> resp.data.splitlines()[0]
'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"'

Or without a wrapper defined:

>>> c = Client(test_app)
>>> app_iter, status, headers = c.get('/')
>>> status
'200 OK'
>>> headers
[('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', '8339')]
>>> ''.join(app_iter).splitlines()[0]
'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"'


Environment Building
====================

.. versionadded:: 0.5

The easiest way to interactively test applications is using the
:class:`EnvironBuilder`.  It can create both standard WSGI environments
and request objects.

The following example creates a WSGI environment with one uploaded file
and a form field:

>>> from werkzeug.test import EnvironBuilder
>>> from StringIO import StringIO
>>> builder = EnvironBuilder(method='POST', data={'foo': 'this is some text',
...      'file': (StringIO('my file contents'), 'test.txt')})
>>> env = builder.get_environ()

The resulting environment is a regular WSGI environment that can be used for
further processing:

>>> from werkzeug.wrappers import Request
>>> req = Request(env)
>>> req.form['foo']
u'this is some text'
>>> req.files['file']
<FileStorage: u'test.txt' ('text/plain')>
>>> req.files['file'].read()
'my file contents'

The :class:`EnvironBuilder` figures out the content type automatically if you
pass a dict to the constructor as `data`.  If you provide a string or an
input stream you have to do that yourself.

By default it will try to use ``application/x-www-form-urlencoded`` and only
use ``multipart/form-data`` if files are uploaded:

>>> builder = EnvironBuilder(method='POST', data={'foo': 'bar'})
>>> builder.content_type
'application/x-www-form-urlencoded'
>>> builder.files['foo'] = StringIO('contents')
>>> builder.content_type
'multipart/form-data'

If a string is provided as data (or an input stream) you have to specify
the content type yourself:

>>> builder = EnvironBuilder(method='POST', data='{"json": "this is"}')
>>> builder.content_type
>>> builder.content_type = 'application/json'


Testing API
===========

.. autoclass:: EnvironBuilder
   :members:

   .. attribute:: path

      The path of the application.  (aka `PATH_INFO`)

   .. attribute:: charset

      The charset used to encode unicode data.

   .. attribute:: headers

      A :class:`Headers` object with the request headers.

   .. attribute:: errors_stream

      The error stream used for the `wsgi.errors` stream.

   .. attribute:: multithread

      The value of `wsgi.multithread`

   .. attribute:: multiprocess

      The value of `wsgi.multiprocess`

   .. attribute:: environ_base

      The dict used as base for the newly create environ.

   .. attribute:: environ_overrides

      A dict with values that are used to override the generated environ.

   .. attribute:: input_stream
    
      The optional input stream.  This and :attr:`form` / :attr:`files`
      is mutually exclusive.  Also do not provide this stream if the
      request method is not `POST` / `PUT` or something comparable.

.. autoclass:: Client

   .. automethod:: open

   Shortcut methods are available for many HTTP methods:

   .. automethod:: get

   .. automethod:: patch

   .. automethod:: post

   .. automethod:: head

   .. automethod:: put

   .. automethod:: delete

   .. automethod:: options

   .. automethod:: trace


.. autofunction:: create_environ([options])

.. autofunction:: run_wsgi_app
