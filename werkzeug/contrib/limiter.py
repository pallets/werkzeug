# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.limiter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    A middleware that limits incoming data.  This works around problems
    with trac or django because those stream into the memory directly.


    :copyright: (c) 2008 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""


class LimitedStream(object):
    """
    Wraps a stream and doesn't read more than n bytes.
    """

    def __init__(self, environ, limit):
        self._environ = environ
        self._stream = environ['wsgi.input']
        self._limit = min(limit, int(environ.get('CONTENT_LENGTH') or 0))
        self._pos = 0

    def read(self, size=None):
        if self._pos >= self._limit:
            return ''
        if size is None:
            size = self._limit
        read = self._stream.read(min(self._limit - self._pos, size))
        self._pos += len(read)
        return read

    def readline(self, *args):
        if self._pos >= self._limit:
            return ''
        line = self._stream.readline(*args)
        self.pos += len(line)
        self.processed()
        return line

    def readlines(self, hint=None):
        result = []
        while self.pos < self._limit:
            result.append(self.readline())
        return result


class StreamLimitMiddleware(object):
    """
    Limits the input stream to a given number of bytes.  This is useful if
    you have a WSGI application that reads form data into memory (django for
    example) and you don't want users to harm the server by uploading tons of
    data.

    Default is 10MB
    """

    def __init__(self, app, maximum_size=1024 * 1024 * 10):
        self.app = app
        self.maximum_size = maximum_size

    def __call__(self, environ, start_response):
        environ['wsgi.input'] = LimitedStream(environ, self.maximum_size)
        return self.app(environ, start_response)
