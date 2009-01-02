# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.profiler
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Provides a WSGI Profiler middleware for finding bottlenecks.

    :copyright: (c) 2008 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import sys
try:
    try:
        from cProfile import Profile
    except ImportError:
        from profile import Profile
    from pstats import Stats
    available = True
except ImportError:
    available = False


class MergeStream(object):
    """An object that redirects `write` calls to multiple streams.
    Use this to log to both `sys.stdout` and a file::

        f = file('profiler.log')
        stream = MergeStream(sys.stdout, f)
        profiler = ProfilerMiddleware(app, stream)
    """

    def __init__(self, *streams):
        if not streams:
            raise TypeError('at least one stream must be given')
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)


class ProfilerMiddleware(object):
    """Simple profiler middleware."""

    def __init__(self, app, stream=None,
                 sort_by=('time', 'calls'), restrictions=()):
        if not available:
            raise RuntimeError('the profiler is not available because '
                               'profile or pstat is not installed.')
        self._app = app
        self._stream = stream or sys.stdout
        self._sort_by = sort_by
        self._restrictions = restrictions

    def __call__(self, environ, start_response):
        response_body = []

        def catching_start_response(status, headers, exc_info=None):
            start_response(status, headers, exc_info)
            return response_body.append

        def runapp():
            appiter = self._app(environ, catching_start_response)
            response_body.extend(appiter)
            if hasattr(appiter, 'close'):
                appiter.close()

        p = Profile()
        p.runcall(runapp)
        body = ''.join(response_body)
        stats = Stats(p)
        stats.sort_stats(*self._sort_by)

        self._stream.write('-' * 80)
        self._stream.write('\nPATH: %r\n' % environ.get('PATH_INFO'))
        stats.print_stats(*self._restrictions)
        self._stream.write('-' * 80 + '\n\n')

        return [body]


def make_action(app_factory, hostname='localhost', port=5000,
                threaded=False, processes=1, stream=None,
                sort_by=('time', 'calls'), restrictions=()):
    """Return a new callback for werkzeug scripts that starts a local
    server for profiling.
    """
    def action(hostname=('h', hostname), port=('p', port),
               threaded=threaded, processes=processes):
        """Start a new development server."""
        from werkzeug.serving import run_simple
        app = ProfilerMiddleware(app_factory(), stream, sort_by, restrictions)
        run_simple(hostname, port, app, False, None, threaded, processes)
    return action
