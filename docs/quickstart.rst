==========
Quickstart
==========

.. module:: werkzeug

This part of the documentation shows how to use the most important parts of
Werkzeug.  It's intended as a starting point for developers with basic
understanding of :pep:`333` (WSGI) and :rfc:`2616` (HTTP).

.. warning::

   Make sure to import all objects from the places the documentation
   suggests.  It is theoretically possible in some situations to import
   objects from different locations but this is not supported.

   For example :class:`MultiDict` is a member of the `werkzeug` module
   but internally implemented in a different one.


WSGI Environment
================

The WSGI environment contains all the information the user request transmits
to the application.  It is passed to the WSGI application but you can also
create a WSGI environ dict using the :func:`create_environ` helper:

>>> from werkzeug.test import create_environ
>>> environ = create_environ('/foo', 'http://localhost:8080/')

Now we have an environment to play around:

>>> environ['PATH_INFO']
'/foo'
>>> environ['SCRIPT_NAME']
''
>>> environ['SERVER_NAME']
'localhost'

Usually nobody wants to work with the environ directly because it is limited
to bytestrings and does not provide any way to access the form data besides
parsing that data by hand.


Enter Request
=============

For access to the request data the :class:`Request` object is much more fun.
It wraps the `environ` and provides a read-only access to the data from
there:

>>> from werkzeug.wrappers import Request
>>> request = Request(environ)

Now you can access the important variables and Werkzeug will parse them
for you and decode them where it makes sense.  The default charset for
requests is set to `utf-8` but you can change that by subclassing
:class:`Request`.

>>> request.path
u'/foo'
>>> request.script_root
u''
>>> request.host
'localhost:8080'
>>> request.url
'http://localhost:8080/foo'

We can also find out which HTTP method was used for the request:

>>> request.method
'GET'

This way we can also access URL arguments (the query string) and data that
was transmitted in a POST/PUT request.

For testing purposes we can create a request object from supplied data
using the :meth:`~BaseRequest.from_values` method:

>>> from cStringIO import StringIO
>>> data = "name=this+is+encoded+form+data&another_key=another+one"
>>> request = Request.from_values(query_string='foo=bar&blah=blafasel',
...    content_length=len(data), input_stream=StringIO(data),
...    content_type='application/x-www-form-urlencoded',
...    method='POST')
...
>>> request.method
'POST'

Now we can access the URL parameters easily:

>>> request.args.keys()
['blah', 'foo']
>>> request.args['blah']
u'blafasel'

Same for the supplied form data:

>>> request.form['name']
u'this is encoded form data'

Handling for uploaded files is not much harder as you can see from this
example::

    def store_file(request):
        file = request.files.get('my_file')
        if file:
            file.save('/where/to/store/the/file.txt')
        else:
            handle_the_error()

The files are represented as :class:`FileStorage` objects which provide
some common operations to work with them.

Request headers can be accessed by using the :class:`~BaseRequest.headers`
attribute:

>>> request.headers['Content-Length']
'54'
>>> request.headers['Content-Type']
'application/x-www-form-urlencoded'

The keys for the headers are of course case insensitive.


Header Parsing
==============

There is more.  Werkzeug provides convenient access to often used HTTP headers
and other request data.

Let's create a request object with all the data a typical web browser transmits
so that we can play with it:

>>> environ = create_environ()
>>> environ.update(
...     HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; U; Mac OS X 10.5; en-US; ) Firefox/3.1',
...     HTTP_ACCEPT='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
...     HTTP_ACCEPT_LANGUAGE='de-at,en-us;q=0.8,en;q=0.5',
...     HTTP_ACCEPT_ENCODING='gzip,deflate',
...     HTTP_ACCEPT_CHARSET='ISO-8859-1,utf-8;q=0.7,*;q=0.7',
...     HTTP_IF_MODIFIED_SINCE='Fri, 20 Feb 2009 10:10:25 GMT',
...     HTTP_IF_NONE_MATCH='"e51c9-1e5d-46356dc86c640"',
...     HTTP_CACHE_CONTROL='max-age=0'
... )
...
>>> request = Request(environ)

Let's start with the most useless header: the user agent:

>>> request.user_agent.browser
'firefox'
>>> request.user_agent.platform
'macos'
>>> request.user_agent.version
'3.1'
>>> request.user_agent.language
'en-US'

A more useful header is the accept header.  With this header the browser
informs the web application what mimetypes it can handle and how well.  All
accept headers are sorted by the quality, the best item being the first:

>>> request.accept_mimetypes.best
'text/html'
>>> 'application/xhtml+xml' in request.accept_mimetypes
True
>>> print request.accept_mimetypes["application/json"]
0.8

The same works for languages:

>>> request.accept_languages.best
'de-at'
>>> request.accept_languages.values()
['de-at', 'en-us', 'en']

And of course encodings and charsets:

>>> 'gzip' in request.accept_encodings
True
>>> request.accept_charsets.best
'ISO-8859-1'
>>> 'utf-8' in request.accept_charsets
True

Normalization is available, so you can safely use alternative forms to perform
containment checking:

>>> 'UTF8' in request.accept_charsets
True
>>> 'de_AT' in request.accept_languages
True

E-tags and other conditional headers are available in parsed form as well:

>>> request.if_modified_since
datetime.datetime(2009, 2, 20, 10, 10, 25)
>>> request.if_none_match
<ETags '"e51c9-1e5d-46356dc86c640"'>
>>> request.cache_control
<RequestCacheControl 'max-age=0'>
>>> request.cache_control.max_age
0
>>> 'e51c9-1e5d-46356dc86c640' in request.if_none_match
True


Responses
=========

Response objects are the opposite of request objects.  They are used to send
data back to the client.  In reality, response objects are nothing more than
glorified WSGI applications.

So what you are doing is not *returning* the response objects from your WSGI
application but *calling* it as WSGI application inside your WSGI application
and returning the return value of that call.

So imagine your standard WSGI "Hello World" application::

    def application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['Hello World!']

With response objects it would look like this::

    from werkzeug.wrappers import Response

    def application(environ, start_response):
        response = Response('Hello World!')
        return response(environ, start_response)

Also, unlike request objects, response objects are designed to be modified.
So here is what you can do with them:

>>> from werkzeug.wrappers import Response
>>> response = Response("Hello World!")
>>> response.headers['content-type']
'text/plain; charset=utf-8'
>>> response.data
'Hello World!'
>>> response.headers['content-length'] = len(response.data)

You can modify the status of the response in the same way.  Either just the
code or provide a message as well:

>>> response.status
'200 OK'
>>> response.status = '404 Not Found'
>>> response.status_code
404
>>> response.status_code = 400
>>> response.status
'400 BAD REQUEST'

As you can see attributes work in both directions.  So you can set both
:attr:`~BaseResponse.status` and :attr:`~BaseResponse.status_code` and the
change will be reflected to the other.

Also common headers are exposed as attributes or with methods to set /
retrieve them:

>>> response.content_length
12
>>> from datetime import datetime
>>> response.date = datetime(2009, 2, 20, 17, 42, 51)
>>> response.headers['Date']
'Fri, 20 Feb 2009 17:42:51 GMT'

Because etags can be weak or strong there are methods to set them:

>>> response.set_etag("12345-abcd")
>>> response.headers['etag']
'"12345-abcd"'
>>> response.get_etag()
('12345-abcd', False)
>>> response.set_etag("12345-abcd", weak=True)
>>> response.get_etag()
('12345-abcd', True)

Some headers are available as mutable structures.  For example most
of the `Content-` headers are sets of values:

>>> response.content_language.add('en-us')
>>> response.content_language.add('en')
>>> response.headers['Content-Language']
'en-us, en'

Also here this works in both directions:

>>> response.headers['Content-Language'] = 'de-AT, de'
>>> response.content_language
HeaderSet(['de-AT', 'de'])

Authentication headers can be set that way as well:

>>> response.www_authenticate.set_basic("My protected resource")
>>> response.headers['www-authenticate']
'Basic realm="My protected resource"'

Cookies can be set as well:

>>> response.set_cookie('name', 'value')
>>> response.headers['Set-Cookie']
'name=value; Path=/'
>>> response.set_cookie('name2', 'value2')

If headers appear multiple times you can use the :meth:`~Headers.getlist`
method to get all values for a header:

>>> response.headers.getlist('Set-Cookie')
['name=value; Path=/', 'name2=value2; Path=/']

Finally if you have set all the conditional values, you can make the
response conditional against a request.  Which means that if the request
can assure that it has the information already, no data besides the headers
is sent over the network which saves traffic.  For that you should set at
least an etag (which is used for comparison) and the date header and then
call :class:`~BaseRequest.make_conditional` with the request object.

The response is modified accordingly (status code changed, response body
removed, entity headers removed etc.)
