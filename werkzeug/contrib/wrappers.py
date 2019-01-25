# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.wrappers
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Extra wrappers or mixins contributed by the community.  These wrappers can
    be mixed in into request objects to add extra functionality.

    Example::

        from werkzeug.wrappers import Request as RequestBase
        from werkzeug.contrib.wrappers import JSONRequestMixin

        class Request(RequestBase, JSONRequestMixin):
            pass

    Afterwards this request object provides the extra functionality of the
    :class:`JSONRequestMixin`.

    :copyright: (c) 2014 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import warnings

from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property
from werkzeug._compat import wsgi_decoding_dance
from werkzeug.wrappers.json import JSONMixin as _JSONMixin
from werkzeug.wrappers import charset as _charset


def is_known_charset(charset):
    """Checks if the given charset is known to Python."""
    warnings.warn(
        "'werkzeug.contrib.wrappers.is_known_charset' has moved to"
        " 'werkzeug.wrappers.charset.is_known_charset'. This old import"
        " will be removed in version 1.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _charset.is_known_charset(charset)


class JSONRequestMixin(_JSONMixin):
    """
    .. deprecated:: 0.15
        Moved to :class:`werkzeug.wrappers.json.JSONMixin`. This old
        import will be removed in version 1.0.
    """

    @property
    def json(self):
        warnings.warn(
            "'werkzeug.contrib.wrappers.JSONRequestMixin' has moved to"
            " 'werkzeug.wrappers.JSONMixin'. This old import will"
            " be removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super(JSONRequestMixin, self).json


class ProtobufRequestMixin(object):

    """Add protobuf parsing method to a request object.  This will parse the
    input data through `protobuf`_ if possible.

    :exc:`~werkzeug.exceptions.BadRequest` will be raised if the content-type
    is not protobuf or if the data itself cannot be parsed property.

    .. _protobuf: https://github.com/protocolbuffers/protobuf
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

    .. _specification: https://wsgi.readthedocs.io/en/latest/specifications/routing_args.html
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


class ReverseSlashBehaviorRequestMixin(object):

    """This mixin reverses the trailing slash behavior of :attr:`script_root`
    and :attr:`path`.  This makes it possible to use :func:`~urlparse.urljoin`
    directly on the paths.

    Because it changes the behavior or :class:`Request` this class has to be
    mixed in *before* the actual request class::

        class MyRequest(ReverseSlashBehaviorRequestMixin, Request):
            pass

    This example shows the differences (for an application mounted on
    `/application` and the request going to `/application/foo/bar`):

        +---------------+-------------------+---------------------+
        |               | normal behavior   | reverse behavior    |
        +===============+===================+=====================+
        | `script_root` | ``/application``  | ``/application/``   |
        +---------------+-------------------+---------------------+
        | `path`        | ``/foo/bar``      | ``foo/bar``         |
        +---------------+-------------------+---------------------+
    """

    @cached_property
    def path(self):
        """Requested path as unicode.  This works a bit like the regular path
        info in the WSGI environment but will not include a leading slash.
        """
        path = wsgi_decoding_dance(self.environ.get('PATH_INFO') or '',
                                   self.charset, self.encoding_errors)
        return path.lstrip('/')

    @cached_property
    def script_root(self):
        """The root path of the script includling a trailing slash."""
        path = wsgi_decoding_dance(self.environ.get('SCRIPT_NAME') or '',
                                   self.charset, self.encoding_errors)
        return path.rstrip('/') + '/'


class DynamicCharsetRequestMixin(_charset.DynamicCharsetRequestMixin):
    """
    .. deprecated:: 0.15
        Moved to :class:`werkzeug.wrappers.charset.DynamicCharsetRequestMixin`.
        This old import will be removed in version 1.0.
    """

    @property
    def charset(self):
        warnings.warn(
            "'werkzeug.contrib.wrappers.DynamicCharsetRequestMixin' has"
            " moved to 'werkzeug.wrappers.charset"
            ".DynamicCharsetRequestMixin'. This old import will be"
            " removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super(DynamicCharsetRequestMixin, self).charset


class DynamicCharsetResponseMixin(_charset.DynamicCharsetResponseMixin):
    """
    .. deprecated:: 0.15
        Moved to :class:`werkzeug.wrappers.charset.DynamicCharsetResponseMixin`.
        This old import will be removed in version 1.0.
    """

    @property
    def charset(self):
        warnings.warn(
            "'werkzeug.contrib.wrappers.DynamicCharsetResponseMixin'"
            " has moved to 'werkzeug.wrappers.charset"
            ".DynamicCharsetResponseMixin'. This old import will be"
            " removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super(DynamicCharsetResponseMixin, self).charset

    @charset.setter
    def charset(self, value):
        warnings.warn(
            "'werkzeug.contrib.wrappers.DynamicCharsetResponseMixin'"
            " has moved to 'werkzeug.wrappers.charset"
            ".DynamicCharsetResponseMixin'. This old import will be"
            " removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        super(DynamicCharsetResponseMixin, type(self)).charset.fset(self, value)
