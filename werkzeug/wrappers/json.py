from __future__ import absolute_import

from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property

try:
    from simplejson import loads
except ImportError:
    from json import loads


class JSONMixin(object):
    """Add json method to a request object. This will parse the input
    data through simplejson if possible.

    :exc:`~werkzeug.exceptions.BadRequest` will be raised if the
    content-type is not json or if the data itself cannot be parsed as
    json.
    """

    @cached_property
    def json(self):
        """Get the result of simplejson.loads if possible."""
        if 'json' not in self.environ.get('CONTENT_TYPE', ''):
            raise BadRequest('Not a JSON request')
        try:
            return loads(self.data.decode(self.charset, self.encoding_errors))
        except Exception:
            raise BadRequest('Unable to read JSON request')
