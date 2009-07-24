# -*- coding: utf-8 -*-
"""
    wzbench
    ~~~~~~~

    A werkzeug internal benchmark module.  It's used in combination with
    hg bisact to find out how the Werkzeug performance of some internal
    core parts changes over time.

    :copyright: 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import division
import os
import sys
import subprocess
from cStringIO import StringIO
from timeit import default_timer as timer

# create a new module were we later store all the werkzeug attributes.
wz = type(sys)('werkzeug_nonlazy')
sys.path.insert(0, '<DUMMY>')


EXPECTED_DELTA = 0.75
TEST_RUNS = 3
MIN_ROUNDS = 10


def find_hg_tag(path):
    tags = {}
    try:
        hgtags = file(os.path.join(path, '.hgtags'))
        try:
            for line in hgtags:
                line = line.strip()
                if not line:
                    continue
                hash, tag = line.split()
                tags[hash] = tag
        finally:
            hgtags.close()
    except IOError:
        pass

    try:
        client = subprocess.Popen(['hg', 'tip', '--template', '#node#'], cwd=path,
                                  stdout=subprocess.PIPE)
    except OSError:
        return

    tip = client.communicate()[0].strip()
    tag = tags.get(tip)
    if tag is not None:
        return tag
    return tip[:12]


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


def bench(func):
    """Times a single function."""
    sys.stdout.write('%44s   ' % func.__name__.replace('_', ' ').title())
    sys.stdout.flush()

    # figure out how many times we have to run the function to
    # get reliable timings.
    def _testrun():
        t = timer()
        for x in xrange(50):
            func()
        return (timer() - t) / 50
    delta = median(_testrun() for x in xrange(6)) or 0.001
    rounds = max(MIN_ROUNDS, int(round(EXPECTED_DELTA / delta)))

    # now run it and calculate the minimal per-iteration time
    def _run():
        t = timer()
        for x in xrange(rounds):
            func()
        return (timer() - t) / rounds * 1000
    delta = min(_run() for x in xrange(TEST_RUNS))
    sys.stdout.write('%.4f\n' % delta)
    sys.stdout.flush()


URL_ENCODED_DATA = 'foo=bar&blah=blub&meh=muh&mah=meh'
MULTIPART_ENCODED_DATA = '\n'.join((
    '--foo',
    'Content-Disposition: form-data; name=foo',
    '',
    'this is just bar',
    '--foo',
    'Content-Disposition: form-data; name=bar',
    '',
    'blafasel',
    '--foo--'
))
MULTIDICT = None


def time_url_decode():
    wz.url_decode(URL_ENCODED_DATA)


def time_parse_form_data_multipart():
    req = wz.Request.from_values(input_stream=StringIO(MULTIPART_ENCODED_DATA),
                                 content_length=len(MULTIPART_ENCODED_DATA),
                                 content_type='multipart/form-data; '
                                              'boundary=foo', method='POST')
    # make sure it's parsed
    req.form



def before_multidict_lookup_hit():
    global MULTIDICT
    MULTIDICT = wz.MultiDict({'foo': 'bar'})

def time_multidict_lookup_hit():
    MULTIDICT['foo']

def after_multidict_lookup_hit():
    global MULTIDICT
    MULTIDICT = None


class Tee(object):

    def __init__(self, file, original):
        self.file = file
        self.original = original

    def flush(self):
        self.original.flush()

    def write(self, x):
        self.file.write(x)
        self.original.write(x)

    def close(self):
        self.file.close()


def main():
    from optparse import OptionParser
    parser = OptionParser(usage='%prog [options]')
    parser.add_option('--werkzeug-path', '-p', dest='path', default='.',
                      help='the path to the werkzeug package. defaults to cwd')
    parser.add_option('--dump', '-d', dest='dump', default=False, action='store_true',
                      help='dump the output into a file for comparison')
    parser.add_option('--compare', '-c', dest='compare', nargs=2,
                      default=False, help='compare the two files specified')
    options, args = parser.parse_args()
    if args:
        parser.error('Script takes no arguments')
    if options.compare:
        compare(*options.compare)
    else:
        options.path = os.path.abspath(options.path)
        wz_version, hg_tag = load_werkzeug(options.path)
        if options.dump:
            dump_filename = '-'.join(filter(None, [wz_version.lower(), hg_tag, 'stats.txt']))
            sys.stdout = Tee(file(dump_filename, 'w'), sys.stdout)
        try:
            run(options.path, wz_version, hg_tag)
        finally:
            if options.dump:
                sys.stdout.close()
                sys.stdout = sys.__stdout__


def compare(file1, file2):
    delim = '-' * 20

    def _error(msg):
        print >> sys.stderr, 'error:', msg
        sys.exit(1)

    def _inner_parse(iterable):
        result = {}
        for line in iterable:
            if line.startswith(delim):
                break
            key, value = line.rsplit(None, 1)
            try:
                result[key] = float(value)
            except ValueError:
                continue
        return result

    def _parse(filename):
        if not os.path.isfile(filename):
            _error('"%s" does not exist' % filename)
        f = file(filename)
        try:
            dc = 0
            for line in f:
                if line.startswith(delim):
                    dc += 1
                    if dc == 2:
                        return _inner_parse(f)
        finally:
            f.close()

    d1 = _parse(file1)
    d2 = _parse(file2)
    if d1.keys() != d2.keys():
        _error('files have different timing keys')

    print '=' * 80
    print 'BENCHMARK COMPARISON'.center(80)
    print '-' * 80
    for key in sorted(d1):
        print '%26s  %.4f    %.4f    % .4f' % (key, d1[key], d2[key],
                                               d1[key] - d2[key])
    print '-' * 80


def run(path, wz_version, hg_tag=None):
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
            bench(value)
            after = globals().get('after_' + key[5:])
            if after:
                after()
    print '-' * 80


if __name__ == '__main__':
    main()

