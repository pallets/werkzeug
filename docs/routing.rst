.. _routing:

===========
URL Routing
===========

.. module:: werkzeug.routing

When it comes to combining multiple controller or view functions (however
you want to call them), you need a dispatcher.  A simple way would be
applying regular expression tests on ``PATH_INFO`` and call registered
callback functions that return the value.

Werkzeug provides a much more powerful system, similar to `Routes`_.  All the
objects mentioned on this page must be imported from :mod:`werkzeug.routing`, not
from :mod:`werkzeug`!

.. _Routes: https://routes.readthedocs.io/en/latest/


Quickstart
==========

Here is a simple example which could be the URL definition for a blog::

    from werkzeug.routing import Map, Rule, NotFound, RequestRedirect

    url_map = Map([
        Rule('/', endpoint='blog/index'),
        Rule('/<int:year>/', endpoint='blog/archive'),
        Rule('/<int:year>/<int:month>/', endpoint='blog/archive'),
        Rule('/<int:year>/<int:month>/<int:day>/', endpoint='blog/archive'),
        Rule('/<int:year>/<int:month>/<int:day>/<slug>',
             endpoint='blog/show_post'),
        Rule('/about', endpoint='blog/about_me'),
        Rule('/feeds/', endpoint='blog/feeds'),
        Rule('/feeds/<feed_name>.rss', endpoint='blog/show_feed')
    ])

    def application(environ, start_response):
        urls = url_map.bind_to_environ(environ)
        try:
            endpoint, args = urls.match()
        except HTTPException, e:
            return e(environ, start_response)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['Rule points to %r with arguments %r' % (endpoint, args)]

So what does that do?  First of all we create a new :class:`Map` which stores
a bunch of URL rules.  Then we pass it a list of :class:`Rule` objects.

Each :class:`Rule` object is instantiated with a string that represents a rule
and an endpoint which will be the alias for what view the rule represents.
Multiple rules can have the same endpoint, but should have different arguments
to allow URL construction.

The format for the URL rules is straightforward, but explained in detail below.

Inside the WSGI application we bind the url_map to the current request which will
return a new :class:`MapAdapter`.  This url_map adapter can then be used to match
or build domains for the current request.

The :meth:`MapAdapter.match` method can then either return a tuple in the form
``(endpoint, args)`` or raise one of the three exceptions
:exc:`~werkzeug.exceptions.NotFound`, :exc:`~werkzeug.exceptions.MethodNotAllowed`,
or :exc:`~werkzeug.exceptions.RequestRedirect`.  For more details about those
exceptions have a look at the documentation of the :meth:`MapAdapter.match` method.


Rule Format
===========

Rule strings basically are just normal URL paths with placeholders in the
format ``<converter(arguments):name>``, where converter and the arguments
are optional.  If no converter is defined, the `default` converter is used
(which means `string` in the normal configuration).

URL rules that end with a slash are branch URLs, others are leaves.  If you
have `strict_slashes` enabled (which is the default), all branch URLs that are
visited without a trailing slash will trigger a redirect to the same URL with
that slash appended.

The list of converters can be extended, the default converters are explained
below.


Builtin Converters
==================

Here a list of converters that come with Werkzeug:

.. autoclass:: UnicodeConverter

.. autoclass:: PathConverter

.. autoclass:: AnyConverter

.. autoclass:: IntegerConverter

.. autoclass:: FloatConverter

.. autoclass:: UUIDConverter


Maps, Rules and Adapters
========================

.. autoclass:: Map
   :members:

   .. attribute:: converters

      The dictionary of converters.  This can be modified after the class
      was created, but will only affect rules added after the
      modification.  If the rules are defined with the list passed to the
      class, the `converters` parameter to the constructor has to be used
      instead.

.. autoclass:: MapAdapter
   :members:

.. autoclass:: Rule
   :members: empty


Rule Factories
==============

.. autoclass:: RuleFactory
   :members: get_rules

.. autoclass:: Subdomain

.. autoclass:: Submount

.. autoclass:: EndpointPrefix


Rule Templates
==============

.. autoclass:: RuleTemplate


Custom Converters
=================

You can add custom converters that add behaviors not provided by the
built-in converters. To make a custom converter, subclass
:class:`BaseConverter` then pass the new class to the :class:`Map`
``converters`` parameter, or add it to
:attr:`url_map.converters <Map.converters>`.

The converter should have a ``regex`` attribute with a regular
expression to match with. If the converter can take arguments in a URL
rule, it should accept them in its ``__init__`` method.

It can implement a ``to_python`` method to convert the matched string to
some other object. This can also do extra validation that wasn't
possible with the ``regex`` attribute, and should raise a
:exc:`werkzeug.routing.ValidationError` in that case. Raising any other
errors will cause a 500 error.

It can implement a ``to_url`` method to convert a Python object to a
string when building a URL. Any error raised here will be converted to a
:exc:`werkzeug.routing.BuildError` and eventually cause a 500 error.

This example implements a ``BooleanConverter`` that will match the
strings ``"yes"``, ``"no"``, and ``"maybe"``, returning a random value
for ``"maybe"``. ::

    from random import randrange
    from werkzeug.routing import BaseConverter, ValidationError

    class BooleanConverter(BaseConverter):
        regex = r"(?:yes|no|maybe)"

        def __init__(self, url_map, maybe=False):
            super(BooleanConverter, self).__init__(url_map)
            self.maybe = maybe

        def to_python(self, value):
            if value == "maybe":
                if self.maybe:
                    return not randrange(2)
                raise ValidationError
            return value == 'yes'

        def to_url(self, value):
            return "yes" if value else "no"

    from werkzeug.routing import Map, Rule

    url_map = Map([
        Rule("/vote/<bool:werkzeug_rocks>", endpoint="vote"),
        Rule("/guess/<bool(maybe=True):foo>", endpoint="guess")
    ], converters={'bool': BooleanConverter})

If you want to change the default converter, assign a different
converter to the ``"default"`` key.


Host Matching
=============

.. versionadded:: 0.7

Starting with Werkzeug 0.7 it's also possible to do matching on the whole
host names instead of just the subdomain.  To enable this feature you need
to pass ``host_matching=True`` to the :class:`Map` constructor and provide
the `host` argument to all routes::

    url_map = Map([
        Rule('/', endpoint='www_index', host='www.example.com'),
        Rule('/', endpoint='help_index', host='help.example.com')
    ], host_matching=True)

Variable parts are of course also possible in the host section::

    url_map = Map([
        Rule('/', endpoint='www_index', host='www.example.com'),
        Rule('/', endpoint='user_index', host='<user>.example.com')
    ], host_matching=True)
