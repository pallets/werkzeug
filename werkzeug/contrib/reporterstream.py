# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.reporterstream
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module implements a class that can wrap `wsgi.input` in order to be
    informed about changes of the stream.  This is useful if you want to
    display a progress bar for the upload.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from warnings import warn
warn(DeprecationWarning('reporter stream is deprecated.  If you want to continue '
                        'using this class copy the module code from the '
                        'werkzeug wiki: http://dev.pocoo.org/projects/werkzeug/'
                        'wiki/ReporterStream'), stacklevel=2)


class BaseReporterStream(object):
    """
    This class can be used to wrap `wsgi.input` in order to be informed about
    changes of the stream.

    Usage::

        from random import randrange

        class ReporterStream(BaseReporterStream):

            def __init__(self, environ):
                super(ReporterStream, self).__init__(environ, 1024 * 16)
                self.transport_id = randrange(0, 100000)

            def processed(self):
                s = self.environ['my.session.service']
                s.store['upload/%s' % self.transport_id] = (self.pos, self.length)
                s.flush()


    And before accessing `request.form` or similar attributes add the stream:

        stream = ReporterStream(environ)
        environ['wsgi.input'] = stream
    """

    def __init__(self, environ, threshold):
        self.threshold = threshold
        self.length = int(environ.get('CONTENT_LENGTH') or 0)
        self.pos = 0
        self.environ = environ
        self._stream = environ['wsgi.input']

    def processed(self):
        """Called after pos has changed for threshold or a line was read."""

    def read(self, size=None):
        length = self.length
        threshold = self.threshold
        buffer = []

        if size is None:
            while self.pos < length:
                step = min(threshold, length - self.pos)
                data = self._stream.read(step)
                self.pos += step
                self.processed()
                buffer.append(data)
        else:
            read = 0
            while read < size:
                step = min(threshold, length - self.pos)
                step = min(step, size)
                data = self._stream.read(step)
                self.pos += step
                read += step
                self.processed()
                buffer.append(data)

        return ''.join(buffer)

    def readline(self, *args):
        line = self._stream.readline(*args)
        self.pos += len(line)
        self.processed()
        return line

    def readlines(self, hint=None):
        result = []
        while self.pos < self.length:
            result.append(self.readline())
        return result
