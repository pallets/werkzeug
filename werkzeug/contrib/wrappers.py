# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.wrappers
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Extra wrappers or mixins contributed by the community.

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
    """Add json method to a request object. This will parse the input data
    through simplejson if possible.

    :exc:`werkzeug.BadRequest` will be raised if the content-type is not json
    or if the data itself cannot be parsed as json.
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
    """Add protobuf method to a request object. This will parse the input data
    through protobuf if possible.

    :exc:`werkzeug.BadRequest` will be raised if the content-type is not
    protobuf or if the data itself cannot be parsed property.
    """

    #: by default the :cls:`ProtobufRequestMixin` will raise a
    #: :exc:`werkzeug.BadRequest` if the object is not initialized.
    #: You can bypass that check by setting this attribute to False.
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
