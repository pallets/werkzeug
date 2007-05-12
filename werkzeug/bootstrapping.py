# -*- coding: utf-8 -*-
"""
    werkzeug.bootstrapping
    ~~~~~~~~~~~~~~~~~~~~~~

    Module that contains some code that is able to create new
    python packages based on templates.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
from fnmatch import fnmatch
from getopt import getopt, GetoptError
from werkzeug.minitmpl import Template


TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATED_FILTERS = ['*.py', '*.html', '*.txt']


def bootstrap(package_name, destination_path, template, charset):
    """
    Do the bootstrapping.
    """
    if os.sep not in template:
        template_path = os.path.join(TEMPLATES, template)
    else:
        template_path = template

    if not os.path.exists(template_path):
        print >>sys.stderr, "Template path not found"
        return -2

    pascal_cased = package_name.title().replace('_', '')

    print 'Generating from "%s"' % template_path

    templated_fn = os.path.join(template_path, '.TEMPLATED')
    templated_filters = []
    if os.path.exists(templated_fn):
        f = file(templated_fn)
        try:
            for line in f:
                templated_filters.append(line.strip())
        finally:
            f.close()
    else:
        templated_filters.extend(TEMPLATED_FILTERS)

    print 'Processing as template: %s' % ', '.join(templated_filters)

    try:
        os.makedirs(destination_path)
    except OSError:
        pass

    context = dict(
        PACKAGE=package_name,
        PACKAGE_PASCAL_CASED=pascal_cased,
        FILE_ENCODING=charset
    )

    offset = len(template_path) + 1
    def walk(p):
        for fn in os.listdir(p):
            if fn.startswith('.'):
                continue
            src_fn = os.path.join(p, fn)
            dst_fn = os.path.join(destination_path, p[offset:], fn) \
                            .replace('PACKAGE', package_name)
            if os.path.isfile(src_fn):
                f = file(src_fn)
                try:
                    data = f.read()
                finally:
                    f.close()
                for pat in templated_filters:
                    if fnmatch(src_fn, pat):
                        tmpl = Template(data.decode('utf-8'))
                        data = tmpl.render(context).encode(charset)
                f = file(dst_fn, 'wb')
                try:
                    f.write(data)
                finally:
                    f.close()
                print '   ' + dst_fn
            else:
                os.mkdir(dst_fn)
                walk(src_fn)
    walk(template_path)

    info_fn = os.path.join(template_path, '.INFO')
    if os.path.exists(info_fn):
        f = file(info_fn)
        try:
            tmpl = Template(f.read().decode('utf-8'))
            msg = tmpl.render(context).encode(sys.stdout.encoding, 'ignore')
        finally:
            f.close()
    else:
        msg = 'Finished template generation'

    print '-' * 79
    print msg
    print '-' * 79

    return 0


def main(args):
    """
    Helper function for the `werkzeug-bootstrapping` script.
    """
    usage = 'Usage: %s [-t <template>] [-c <charset>] ' \
            '<package> <dst>' % os.path.basename(args[0])
    try:
        optlist, args = getopt(args[1:], 't:c:')
    except GetoptError, err:
        args = []
    if len(args) not in (1, 2):
        print >>sys.stderr, usage
        return -1
    options = dict(optlist)

    charset = options.get('-c') or 'utf-8'
    template = options.get('-t') or 'werkzeug_default'
    package = args.pop(0)
    dst = args and args[0] or '.'

    return bootstrap(package, dst, template, charset)
