# -*- coding: utf-8 -*-
"""
    werkzeug.test
    ~~~~~~~~~~~~~

    Helper module for unittests.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from time import time
from random import random
from urllib import urlencode
from cStringIO import StringIO
from mimetypes import guess_type
from werkzeug.wrappers import BaseResponse
from werkzeug.utils import create_environ, run_wsgi_app


def encode_multipart(values):
    """
    Encode a dict of values (can either be strings or file descriptors)
    into a multipart encoded string.  The filename is taken from the `.name`
    attribute of the file descriptor.  Because StringIOs do not provide
    this attribute it will generate a random filename in that case.

    The return value is a tuple in the form (``boundary``, ``data``).

    This method does not accept unicode strings!
    """
    boundary = '-----------=_Part_%s%s' (time(), random())
    lines = []
    for key, value in values.iteritems():
        if isinstance(value, File):
            lines.extend((
                '--' + boundary,
                'Content-Dispotion: form-data; name="%s"; filename="%s"' %
                    (key, value.filename),
                'Content-Type: ' + value.mimetype,
                '',
                value.read()
            ))
        else:
            lines.extend((
                '--' + boundary,
                'Content-Dispotion: form-data; name="%s"' % key,
                '',
                value
            ))
    lines.extend(('--' + boundary + '--', ''))
    return boundary, '\r\n'.join(lines)


class File(object):
    """
    Wraps a file descriptor or any other stream so that `encode_multipart`
    can get the mimetype and filename from it.
    """

    def __init__(self, fd, filename=None, mimetype=None):
        if isinstance(fd, basestring):
            if filename is None:
                filename = fd
            fd = file(fd, 'rb')
            try:
                self.stream = StringIO(fd.read())
            finally:
                fd.close()
        else:
            self.stream = fd
            if filename is None:
                if not hasattr(fd, 'name'):
                    raise ValueError('no filename for provided')
                filename = fd.name
        if mimetype is None:
            mimetype = guess_type(filename)
        self.filename = fileanme
        self.mimetype = mimetype or 'application/octet-stream'

    def getattr(self, name):
        return getattr(self.stream, name)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.filename
        )


class Client(object):
    """
    This class allows to send requests to a wrapped application.
    """

    def __init__(self, application, response_wrapper=None):
        """
        The response wrapper can be a class or factory function that takes
        three arguments: app_iter, status and headers.  The default response
        wrapper just returns a tuple.

        Example::

            class ClientResponse(BaseResponse):
                ...

            client = Client(MyApplication(), response_wrapper=ClientResponse)
        """
        self.application = application
        if response_wrapper is None:
            response_wrapper = lambda a, s, h: (a, s, h)
        self.response_wrapper = response_wrapper

    def open(self, path='/', base_url=None, query_string=None, method='GET',
             data=None, input_stream=None, content_type=None,
             content_length=0, errors_stream=None, multithread=False,
             multiprocess=False, run_once=False, environ_overrides=None):
        """
        Open a page for the application.  This function takes similar
        arguments as the `create_environ` method from the utils module.  If
        the first argument is an environ or request object it is used as
        the environment for the request.
        """
        if input_stream is None and data and method in ('PUT', 'POST'):
            need_multipart = False
            for key, value in data.iteritems():
                if isinstance(value, basestring):
                    if isinstance(value, unicode):
                        data[key] = str(value)
                    continue
                need_multipart = True
                if isinstance(value, tuple):
                    data[key] = File(*value)
                elif isinstance(value, dict):
                    data[key] = File(**value)
                elif not isinstance(value, File):
                    data[key] = File(value)
            if need_multipart:
                boundary, data = encode_multipart(data)
                content_type = 'multipart/form-data; boundary=' + boundary
            else:
                data = urlencode(data)
                content_type = 'application/x-www-form-urlencoded'
            content_length = len(data)
            input_stream = StringIO(data)

        if hasattr(path, 'environ'):
            environ = path.environ
        elif isinstance(path, dict):
            environ = path
        else:
            environ = create_environ(path, base_url, query_string, method,
                                     input_stream, content_type, content_length,
                                     errors_stream, multithread,
                                     multiprocess, run_once)
        if environ_overrides:
            environ.update(environ_overrides)
        rv = run_wsgi_app(self.application, environ)
        return self.response_wrapper(*rv)

    def get(self, *args, **kw):
        """Like open but method is enforced to GET"""
        kw['method'] = 'GET'
        return self.open(*args, **kw)

    def post(self, *args, **kw):
        """Like open but method is enforced to POST"""
        kw['method'] = 'POST'
        return self.open(*args, **kw)

    def head(self, *args, **kw):
        """Like open but method is enforced to HEAD"""
        kw['method'] = 'HEAD'
        return self.open(*args, **kw)

    def put(self, *args, **kw):
        """Like open but method is enforced to PUT"""
        kw['method'] = 'PUT'
        return self.open(*args, **kw)

    def delete(self, *args, **kw):
        """Like open but method is enforced to DELETE"""
        kw['method'] = 'DELETE'
        return self.open(*args, **kw)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.application
        )
