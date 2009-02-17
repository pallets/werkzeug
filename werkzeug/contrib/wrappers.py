# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.wrappers
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Extra wrappers or mixins contributed by the community.  These wrappers can
    be mixed in into request objects to add extra functionality.

    Example::

        from werkzeug import Request as RequestBase
        from werkzeug.contrib.wrappers import JSONRequestMixin

        class Request(RequestBase, JSONRequestMixin):
            pass

    Afterwards this request object provides the extra functionality of the
    :class:`JSONRequestMixin`.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property
try:
    from simplejson import loads
except ImportError:
    from json import loads


class JSONRequestMixin(object):
    """Add json method to a request object.  This will parse the input data
    through simplejson if possible.

    :exc:`~werkzeug.exceptions.BadRequest` will be raised if the content-type
    is not json or if the data itself cannot be parsed as json.
    """

    @cached_property
    def json(self):
        """Get the result of simplejson.loads if possible."""
        if 'json' not in self.environ.get('CONTENT_TYPE', ''):
            raise BadRequest('Not a JSON request')
        try:
            return loads(self.data)
        except Exception:
            raise BadRequest('Unable to read JSON request')


class ProtobufRequestMixin(object):
    """Add protobuf parsing method to a request object.  This will parse the
    input data through `protobuf`_ if possible.

    :exc:`~werkzeug.exceptions.BadRequest` will be raised if the content-type
    is not protobuf or if the data itself cannot be parsed property.

    .. _protobuf: http://code.google.com/p/protobuf/
    """

    #: by default the :class:`ProtobufRequestMixin` will raise a
    #: :exc:`~werkzeug.exceptions.BadRequest` if the object is not
    #: initialized.  You can bypass that check by setting this
    #: attribute to `False`.
    protobuf_check_initialization = True

    def parse_protobuf(self, proto_type):
        """Parse the data into an instance of proto_type."""
        if 'protobuf' not in self.environ.get('CONTENT_TYPE', ''):
            raise BadRequest('Not a Protobuf request')

        obj = proto_type()
        try:
            obj.ParseFromString(self.data)
        except Exception:
            raise BadRequest("Unable to parse Protobuf request")

        # Fail if not all required fields are set
        if self.protobuf_check_initialization and not obj.IsInitialized():
            raise BadRequest("Partial Protobuf request")

        return obj


class RoutingArgsRequestMixin(object):
    """This request mixin adds support for the wsgiorg routing args
    `specification`_.

    .. _specification: http://www.wsgi.org/wsgi/Specifications/routing_args
    """

    def _get_routing_args(self):
        return self.environ.get('wsgiorg.routing_args', (()))[0]

    def _set_routing_args(self, value):
        if self.shallow:
            raise RuntimeError('A shallow request tried to modify the WSGI '
                               'environment.  If you really want to do that, '
                               'set `shallow` to False.')
        self.environ['wsgiorg.routing_args'] = (value, self.routing_vars)

    routing_args = property(_get_routing_args, _set_routing_args, doc='''
        The positional URL arguments as `tuple`.''')
    del _get_routing_args, _set_routing_args

    def _get_routing_vars(self):
        rv = self.environ.get('wsgiorg.routing_args')
        if rv is not None:
            return rv[1]
        rv = {}
        if not self.shallow:
            self.routing_vars = rv
        return rv

    def _set_routing_vars(self, value):
        if self.shallow:
            raise RuntimeError('A shallow request tried to modify the WSGI '
                               'environment.  If you really want to do that, '
                               'set `shallow` to False.')
        self.environ['wsgiorg.routing_args'] = (self.routing_args, value)

    routing_vars = property(_get_routing_vars, _set_routing_vars, doc='''
        The keyword URL arguments as `dict`.''')
    del _get_routing_vars, _set_routing_vars
