#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    wzbench
    ~~~~~~~

    A werkzeug internal benchmark module.  It's used in combination with
    hg bisect to find out how the Werkzeug performance of some internal
    core parts changes over time.

    :copyright: 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import division
import os
import gc
import sys
import subprocess
from cStringIO import StringIO
from timeit import default_timer as timer
from types import FunctionType


# create a new module where we later store all the werkzeug attributes.
wz = type(sys)('werkzeug_nonlazy')
sys.path.insert(0, '<DUMMY>')
null_out = file(os.devnull, 'w')


# ±4% are ignored
TOLERANCE = 0.04
MIN_RESOLUTION = 0.002

# we run each test 5 times
TEST_RUNS = 5


def find_hg_tag(path):
    """Returns the current node or tag for the given path."""
    tags = {}
    try:
        client = subprocess.Popen(['hg', 'cat', '-r', 'tip', '.hgtags'],
                                  stdout=subprocess.PIPE, cwd=path)
        for line in client.communicate()[0].splitlines():
            line = line.strip()
            if not line:
                continue
            hash, tag = line.split()
            tags[hash] = tag
    except OSError:
        return

    client = subprocess.Popen(['hg', 'parent', '--template', '#node#'],
                              stdout=subprocess.PIPE, cwd=path)

    tip = client.communicate()[0].strip()
    tag = tags.get(tip)
    if tag is not None:
        return tag
    return tip


def load_werkzeug(path):
    """Load werkzeug."""
    sys.path[0] = path

    # get rid of already imported stuff
    wz.__dict__.clear()
    for key in sys.modules.keys():
        if key.startswith('werkzeug.') or key == 'werkzeug':
            sys.modules.pop(key, None)

    # import werkzeug again.
    import werkzeug
    for key in werkzeug.__all__:
        setattr(wz, key, getattr(werkzeug, key))

    # get the hg tag
    hg_tag = find_hg_tag(path)

    # get the real version from the setup file
    try:
        f = file(os.path.join(path, 'setup.py'))
    except IOError:
        pass
    else:
        try:
            for line in f:
                line = line.strip()
                if line.startswith('version='):
                    return line[8:].strip(' \t,')[1:-1], hg_tag
        finally:
            f.close()
    print >> sys.stderr, 'Unknown werkzeug version loaded'
    sys.exit(2)


def median(seq):
    seq = sorted(seq)
    if not seq:
        return 0.0
    return seq[len(seq) // 2]


def format_func(func):
    if type(func) is FunctionType:
        name = func.__name__
    else:
        name = func
    if name.startswith('time_'):
        name = name[5:]
    return name.replace('_', ' ').title()


def bench(func):
    """Times a single function."""
    sys.stdout.write('%44s   ' % format_func(func))
    sys.stdout.flush()

    # figure out how many times we have to run the function to
    # get reliable timings.
    for i in xrange(3, 10):
        rounds = 1 << i
        t = timer()
        for x in xrange(rounds):
            func()
        if timer() - t >= 0.2:
            break

    # now run the tests without gc TEST_RUNS times and use the median
    # value of these runs.
    def _run():
        gc.collect()
        gc.disable()
        try:
            t = timer()
            for x in xrange(rounds):
                func()
            return (timer() - t) / rounds * 1000
        finally:
            gc.enable()

    delta = median(_run() for x in xrange(TEST_RUNS))
    sys.stdout.write('%.4f\n' % delta)
    sys.stdout.flush()

    return delta


def main():
    """The main entrypoint."""
    from optparse import OptionParser
    parser = OptionParser(usage='%prog [options]')
    parser.add_option('--werkzeug-path', '-p', dest='path', default='..',
                      help='the path to the werkzeug package. defaults to cwd')
    parser.add_option('--compare', '-c', dest='compare', nargs=2,
                      default=False, help='compare two hg nodes of Werkzeug')
    parser.add_option('--init-compare', dest='init_compare',
                      action='store_true', default=False,
                      help='Initializes the comparison feature')
    options, args = parser.parse_args()
    if args:
        parser.error('Script takes no arguments')
    if options.compare:
        compare(*options.compare)
    elif options.init_compare:
        init_compare()
    else:
        run(options.path)


def init_compare():
    """Initializes the comparison feature."""
    print 'Initializing comparison feature'
    subprocess.Popen(['hg', 'clone', '..', 'a']).wait()
    subprocess.Popen(['hg', 'clone', '..', 'b']).wait()


def compare(node1, node2):
    """Compares two Werkzeug hg versions."""
    if not os.path.isdir('a'):
        print >> sys.stderr, 'error: comparison feature not initialized'
        sys.exit(4)

    print '=' * 80
    print 'WERKZEUG INTERNAL BENCHMARK -- COMPARE MODE'.center(80)
    print '-' * 80

    delim = '-' * 20

    def _error(msg):
        print >> sys.stderr, 'error:', msg
        sys.exit(1)

    def _hg_update(repo, node):
        hg = lambda *x: subprocess.call(['hg'] + list(x), cwd=repo,
                                        stdout=null_out, stderr=null_out)
        hg('revert', '-a', '--no-backup')
        client = subprocess.Popen(['hg', 'status', '--unknown', '-n', '-0'],
                                  stdout=subprocess.PIPE, cwd=repo)
        unknown = client.communicate()[0]
        if unknown:
            client = subprocess.Popen(['xargs', '-0', 'rm', '-f'], cwd=repo,
                                      stdout=null_out, stdin=subprocess.PIPE)
            client.communicate(unknown)
        hg('pull', '../..')
        hg('update', node)
        if node == 'tip':
            diff = subprocess.Popen(['hg', 'diff'], cwd='..',
                                    stdout=subprocess.PIPE).communicate()[0]
            if diff:
                client = subprocess.Popen(['hg', 'import', '--no-commit', '-'],
                                          cwd=repo, stdout=null_out,
                                          stdin=subprocess.PIPE)
                client.communicate(diff)

    _hg_update('a', node1)
    _hg_update('b', node2)
    d1 = run('a', no_header=True)
    d2 = run('b', no_header=True)

    print 'DIRECT COMPARISON'.center(80)
    print '-' * 80
    for key in sorted(d1):
        delta = d1[key] - d2[key]
        if abs(1 - d1[key] / d2[key]) < TOLERANCE or \
           abs(delta) < MIN_RESOLUTION:
            delta = '=='
        else:
            delta = '%+.4f (%+d%%)' % \
                        (delta, round(d2[key] / d1[key] * 100 - 100))
        print '%36s   %.4f    %.4f    %s' % \
                        (format_func(key), d1[key], d2[key], delta)
    print '-' * 80


def run(path, no_header=False):
    path = os.path.abspath(path)
    wz_version, hg_tag = load_werkzeug(path)
    result = {}
    if not no_header:
        print '=' * 80
        print 'WERKZEUG INTERNAL BENCHMARK'.center(80)
        print '-' * 80
    print 'Path:    %s' % path
    print 'Version: %s' % wz_version
    if hg_tag is not None:
        print 'HG Tag:  %s' % hg_tag
    print '-' * 80
    for key, value in sorted(globals().items()):
        if key.startswith('time_'):
            before = globals().get('before_' + key[5:])
            if before:
                before()
            result[key] = bench(value)
            after = globals().get('after_' + key[5:])
            if after:
                after()
    print '-' * 80
    return result


URL_DECODED_DATA = dict((str(x), str(x)) for x in xrange(100))
URL_ENCODED_DATA = '&'.join('%s=%s' % x for x in URL_DECODED_DATA.items())
MULTIPART_ENCODED_DATA = '\n'.join((
    '--foo',
    'Content-Disposition: form-data; name=foo',
    '',
    'this is just bar',
    '--foo',
    'Content-Disposition: form-data; name=bar',
    '',
    'blafasel',
    '--foo',
    'Content-Disposition: form-data; name=foo; filename=wzbench.py',
    'Content-Type: text/plain',
    '',
    file(__file__.rstrip('c')).read(),
    '--foo--'
))
MULTIDICT = None
REQUEST = None
TEST_ENV = None
LOCAL = None
LOCAL_MANAGER = None


def time_url_decode():
    wz.url_decode(URL_ENCODED_DATA)


def time_url_encode():
    wz.url_encode(URL_DECODED_DATA)


def time_parse_form_data_multipart():
    # use a hand written env creator so that we don't bench
    # from_values which is known to be slowish in 0.5.1 and higher.
    # we don't want to bench two things at once.
    environ = {
        'REQUEST_METHOD':   'POST',
        'CONTENT_TYPE':     'multipart/form-data; boundary=foo',
        'wsgi.input':       StringIO(MULTIPART_ENCODED_DATA),
        'CONTENT_LENGTH':   str(len(MULTIPART_ENCODED_DATA))
    }
    request = wz.Request(environ)
    request.form


def before_multidict_lookup_hit():
    global MULTIDICT
    MULTIDICT = wz.MultiDict({'foo': 'bar'})

def time_multidict_lookup_hit():
    MULTIDICT['foo']

def after_multidict_lookup_hit():
    global MULTIDICT
    MULTIDICT = None


def before_multidict_lookup_miss():
    global MULTIDICT
    MULTIDICT = wz.MultiDict()

def time_multidict_lookup_miss():
    try:
        MULTIDICT['foo']
    except KeyError:
        pass

def after_multidict_lookup_miss():
    global MULTIDICT
    MULTIDICT = None


def time_cached_property():
    class Foo(object):
        @wz.cached_property
        def x(self):
            return 42

    f = Foo()
    for x in xrange(60):
        f.x


def before_request_form_access():
    global REQUEST
    data = 'foo=bar&blah=blub'
    REQUEST = wz.Request({
        'CONTENT_LENGTH':        str(len(data)),
        'wsgi.input':            StringIO(data),
        'REQUEST_METHOD':        'POST',
        'wsgi.version':          (1, 0),
        'QUERY_STRING':          data,
        'CONTENT_TYPE':          'application/x-www-form-urlencoded',
        'PATH_INFO':             '/',
        'SCRIPT_NAME':           ''
    })

def time_request_form_access():
    for x in xrange(30):
        REQUEST.path
        REQUEST.script_root
        REQUEST.args['foo']
        REQUEST.form['foo']

def after_request_form_access():
    global REQUEST
    REQUEST = None


def time_request_from_values():
    wz.Request.from_values(base_url='http://www.google.com/',
                           query_string='foo=bar&blah=blaz',
                           input_stream=StringIO(MULTIPART_ENCODED_DATA),
                           content_length=len(MULTIPART_ENCODED_DATA),
                           content_type='multipart/form-data; '
                                        'boundary=foo', method='POST')


def before_request_shallow_init():
    global TEST_ENV
    TEST_ENV = wz.create_environ()


def time_request_shallow_init():
    wz.Request(TEST_ENV, shallow=True)


def after_request_shallow_init():
    global TEST_ENV
    TEST_ENV = None


def time_response_iter_performance():
    resp = wz.Response(u'Hällo Wörld ' * 1000,
                       mimetype='text/html')
    for item in resp({'REQUEST_METHOD': 'GET'}, lambda *s: None):
        pass


def time_response_iter_head_performance():
    resp = wz.Response(u'Hällo Wörld ' * 1000,
                       mimetype='text/html')
    for item in resp({'REQUEST_METHOD': 'HEAD'}, lambda *s: None):
        pass


def before_local_manager_dispatch():
    global LOCAL_MANAGER, LOCAL
    LOCAL = wz.Local()
    LOCAL_MANAGER = wz.LocalManager([LOCAL])


def time_local_manager_dispatch():
    for x in xrange(10):
        LOCAL.x = 42
    for x in xrange(10):
        LOCAL.x


def after_local_manager_dispatch():
    global LOCAL_MANAGER, LOCAL
    LOCAL = LOCAL_MANAGER = None


def before_html_builder():
    global TABLE
    TABLE = [['col 1', 'col 2', 'col 3', '4', '5', '6'] for x in range(10)]


def time_html_builder():
    html_rows = []
    for row in TABLE:
        html_cols = [wz.html.td(col, class_='col') for col in row]
        html_rows.append(wz.html.tr(class_='row', *html_cols))
    table = wz.html.table(*html_rows)


def after_html_builder():
    global TABLE
    TABLE = None


if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__) or os.path.curdir)
    try:
        main()
    except KeyboardInterrupt:
        print >> sys.stderr, 'interrupted!'
