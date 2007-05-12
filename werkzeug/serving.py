# -*- coding: utf-8 -*-
"""
    werkzeug.serving
    ~~~~~~~~~~~~~~~~

    Helper module used by `werkzeug-serve`. Because there is no working
    way without sideeffects to reload python applications while they
    are running this module wraps a starter script.

    Create a file ``start.py`` with something like this in::

        #!/usr/bin/env werkzeug-serve
        from myapplication import make_app
        application = make_app()

    And and then run it with ``./start.py`` after you gave it the executable
    bit. The object called `application` is used as WSGI application.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import time
import subprocess
import tempfile
from thread import start_new_thread
from getopt import getopt, GetoptError


def _reloader_loop(extra_files):
    """When this function is run from the main thread, it will force other
    threads to exit when any modules currently loaded change.

    :param extra_files: a list of additional files it should watch.
    """
    mtimes = {}
    while True:
        for filename in filter(None, [getattr(module, '__file__', None)
                                      for module in sys.modules.values()] +
                                     extra_files):
            while not os.path.isfile(filename):
                filename = os.path.dirname(filename)
                if not filename:
                    break
            if not filename:
                continue

            if filename[-4:] in ('.pyc', '.pyo'):
                filename = filename[:-1]

            mtime = os.stat(filename).st_mtime
            if filename not in mtimes:
                mtimes[filename] = mtime
                continue
            if mtime > mtimes[filename]:
                sys.exit(3)
        time.sleep(1)


def act_as_host(app, starter, hostname, port, do_reload):
    """
    Helper for the `werkzeug-serve` script.
    """
    def inner():
        from wsgiref.simple_server import make_server
        srv = make_server(hostname, port, app)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    if do_reload:
        start_new_thread(inner, ())
        try:
            _reloader_loop([starter])
        except KeyboardInterrupt:
            pass
    else:
        inner()


def run(hostname, port, starter_name, do_reload):
    f = file(starter_name)
    try:
        code = f.read()
    finally:
        f.close()
    code += '\n\ntry:\n' \
            '    application\n' \
            'except NameError:\n' \
            '    import sys\n' \
            '    sys.stderr.write("No application specified\\n")\n' \
            '    sys.exit(1)\n' \
            'from werkzeug import serving\n' \
            'serving.act_as_host(application, __file__, %r, %r, %r)' % \
            (hostname, port, do_reload)
    f = tempfile.NamedTemporaryFile()
    f.write(code)
    f.flush()

    print 'Serving on http://%s:%d/' % (hostname, port)
    if do_reload:
        print 'automatic reloader enabled'

    while 1:
        try:
            retcode = subprocess.call([sys.executable, f.name])
        except KeyboardInterrupt:
            retcode = -1
        if retcode != 3:
            break


def main(args):
    """
    Helper function for the `werkzeug-serve` script.
    """
    usage = 'Usage: %s -r [-h <hostname>] [-p <port>] <starter>' % \
            os.path.basename(args[0])
    try:
        optlist, args = getopt(args[1:], 'rh:p:')
    except GetoptError, err:
        args = []
    if len(args) != 1:
        print >>sys.stderr, usage
        return -1
    options = dict(optlist)

    hostname = options.get('-h') or 'localhost'
    try:
        port = int(options.get('-p') or '5000')
    except ValueError:
        print >>sys.stderr, 'ERROR: port must be an interger'
        return -2

    run(hostname, port, args[0], '-r' in options)


if __name__ == '__main__':
    print "FOO"
