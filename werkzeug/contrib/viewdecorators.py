# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.viewdecorators
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Convenience decorators for view callables to return common responses.

    For details on HTTP status codes, see :rfc:`2616`.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from functools import wraps

try:
    import simplejson as json
except ImportError:
    import json

from werkzeug.wrappers import Response


def jsonify(func):
    """Return data as JSON response.

    Data returned by the decorated callable is transformed to JSON and wrapped
    in a response with the appropriate MIME type (as defined in :rfc:`4627`).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = json.dumps(func(*args, **kwargs))
        return Response(data, mimetype='application/json')
    return wrapper


def respond_created(func):
    """Return a ``201 Created`` response.

    The decorated callable is expected to return the URL of the newly created
    resource.  That URL is then added to the response as ``Location:`` header.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        url = func(*args, **kwargs)
        return Response(status=201, headers=[('Location', url)])
    return wrapper


def respond_no_content(func):
    """Send a ``204 No Content`` response."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        return Response(status=204)
    return wrapper
