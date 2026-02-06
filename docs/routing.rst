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
        except HTTPException as e:
            return e(environ, start_response)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [f'Rule points to {endpoint!r} with arguments {args!r}'.encode()]

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

Rule strings are URL paths with placeholders for variable parts in the
format ``<converter(arguments):name>``. ``converter`` and ``arguments``
(with parentheses) are optional. If no converter is given, the
``default`` converter is used (``string`` by default). The available
converters are discussed below.

Rule path parts are separated by ``/`` and matched individually, unless a
converter opts in to matching ``/`` as well.

Rules that end with a slash are "branches", others are "leaves". If
``strict_slashes`` is enabled (the default), visiting a branch URL
without a trailing slash will redirect to the URL with a slash appended.

Many HTTP servers merge consecutive slashes into one when receiving
requests. If ``merge_slashes`` is enabled (the default), rules will
merge slashes in non-variable parts when matching and building. Visiting
a URL with consecutive slashes will redirect to the URL with slashes
merged. If you want to disable ``merge_slashes`` for a :class:`Rule` or
:class:`Map`, you'll also need to configure your web server
appropriately.

Besides the path, matching can also use the subdomain of a known base domain if
``subdomain_matching`` is enabled (the default), or the full host (if
``host_matching`` is enabled). The subdomain or host parts can also contain
variables. Unlike the path, where multiple parts are separated by ``/``, the
domain is always matched as a single part.

If a duplicate rule is added to a map, a :exc:`.DuplicateRuleError` will be
raised. Rules are compared based on their path, subdomain or host, and websocket
mode. Variable parts are not equal if they use different converters, although
this heuristic may not be perfect depending on what the different converters can
actually match.


Rule Priority
=============

In general, the map matches more specific rules first. Rules are made up of
static and variable parts, separated by slash ``/``. For a given segment, rules
with a static part in that position take priority, and longer static values take
priority over shorter. Variable parts are weighted based on the type of data
they match.

If you're using subdomain or host matching, the domain part can use converters
as well. The domain part is matched before the path parts. Like the path parts,
a static domain part take priority over a variable part.

Rules may end up with the same priority, by having static parts with the same
length, and dynamic parts with the same weight, in the same positions. In this
case, sorting is stable, so rules added earlier take priority.

The exact way that rules are sorted internally is pretty complicated, but the
result should be that you can rely on more specific rules matching before more
general ones.


Built-in Converters
===================

Converters for common types of URL variables are built-in. The available
converters can be overridden or extended through :attr:`Map.converters`.

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

.. currentmodule:: werkzeug.routing.exceptions

.. autoclass:: DuplicateRuleError
    :members:


Rule Factories
==============

.. currentmodule:: werkzeug.routing

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
rule, it should accept them in its ``__init__`` method. The entire
regex expression will be matched as a group and used as the value for
conversion.

If a custom converter can match a forward slash, ``/``, it should have
the attribute ``part_isolating`` set to ``False``. This will ensure
that rules using the custom converter are correctly matched.

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
            super().__init__(url_map)
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


Subdomain or Host Matching
==========================

It's possible to route based on the domain part of the URL, in addition
to the path. There are two ways to match, by subdomains under a single domain,
or by full domains.

Subdomain Matching
------------------

Subdomain matching is the more common approach, and is enabled by default.
In order to route by subdomain, pass the ``subdomain`` argument to
:class:`Rule`. It can use converters just like the path part of the rule can.

.. code-block:: python

    from werkzeug import Request, Response
    from werkzeug.routing import Map, Rule

    url_map = Map([
        Rule("/", endpoint="base"),
        Rule("/", endpoint="support", subdomain="support"),
        Rule("/<word>", endpoint="word", subdomain="<language>"),
    ])

    @Request.application
    def app(request: Request) -> Response:
        urls = url_map.bind_to_environ(request, server_name="app.example")
        endpoint, args = urls.match()
        # for the word endpoint, args will contain "language" and "word"
        ...

You can also use the :class:`Subdomain` rule factory to apply a subdomain rule
automatically to a list of rules.

If a rule doesn't specify a ``subdomain`` part, it will use the
:attr:`Map.default_subdomain`. This defaults to empty, meaning it will match on
the base domain only. In order for the routing to know the subdomain, you must
pass the base ``server_name`` when calling :meth:`Map.bind_to_environ`. If the
map cannot determine the subdomain, such as when accessing by IP or an alternate
domain name, it will also default to :attr:`Map.default_subdomain`.

It's also possible to disable any domain-based routing, by passing
``subdomain_matching=False`` when creating the :class:`Map` (``host_matching``
defaults to false).

Host Matching
-------------

If your application is intended to be accessed from separate domains, rather
than subdomains, you can use host matching instead. Pass ``host_matching=True``
when creating the :class:`Map` to enable it, and pass the ``host`` argument to
:class:`Rule`. It can use converters just like the path part of the rule can.

.. code-block:: python

    from werkzeug import Request, Response
    from werkzeug.routing import Map, Rule

    url_map = Map([
        Rule("/", endpoint="company", host="company.example"),
        Rule("/", endpoint="user", host="<user>.app.example"),
    ])

    @Request.application
    def app(request: Request) -> Response:
        urls = url_map.bind_to_environ(request)
        endpoint, args = urls.match()
        # for the user endpoint, args will contain "user"
        ...

Enabling ``host_matching`` disables ``subdomain_matching``, as matching
subdomains is a subset of matching hosts. That is, if you also want to match
subdomains, you still can by specifying the full domain rather than only the
prefix.

The ``Host`` header used for this matching also includes the port if it's
non-standard (HTTP 80, HTTPS 443). This means that you can route based on port
as well; however it also means that when running the development server the port
will be 5000 (by default) and the rules would need to be updated. You could
write a small helper to append the correct port based on configuration when
creating rules, or you could add an HTTP server as described in
:doc:`deployment/index` to proxy the port.


WebSockets
==========

.. versionadded:: 1.0

If a :class:`Rule` is created with ``websocket=True``, it will only
match if the :class:`Map` is bound to a request with a ``url_scheme`` of
``ws`` or ``wss``.

.. note::

   Werkzeug has no further WebSocket support beyond routing. This
   functionality is mostly of use to ASGI projects.

.. code-block:: python

    url_map = Map([
        Rule("/ws", endpoint="comm", websocket=True),
    ])
    adapter = map.bind("example.org", "/ws", url_scheme="ws")
    assert adapter.match() == ("comm", {})

If the only match is a WebSocket rule and the bind is HTTP (or the
only match is HTTP and the bind is WebSocket) a
:exc:`WebsocketMismatch` (derives from
:exc:`~werkzeug.exceptions.BadRequest`) exception is raised.

As WebSocket URLs have a different scheme, rules are always built with a
scheme and host, ``force_external=True`` is implied.

.. code-block:: python

    url = adapter.build("comm")
    assert url == "ws://example.org/ws"
