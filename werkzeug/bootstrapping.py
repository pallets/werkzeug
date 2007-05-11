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
from getopt import getopt, GetoptError
from werkzeug.minitmpl import Template


TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')


def bootstrap(package_name, destination_path, template, charset):
    """
    Do the bootstrapping.
    """
    if os.sep not in template:
        template_path = os.path.join(TEMPLATES, template)
    else:
        template_path = template
    pascal_cased = package_name.title().replace('_', '')

    print 'Generating from "%s"' % template_path


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
                    tmpl = Template(f.read().decode('utf-8'))
                finally:
                    f.close()
                f = file(dst_fn, 'w')
                try:
                    f.write(tmpl.render(context).encode(charset))
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
    usage = 'Usage: %s [-t <template>] [-c <charset>] ' \
            '<package> <dst>' % os.path.basename(args[0])
    try:
        optlist, args = getopt(args[1:], 't:c:')
    except GetoptError, err:
        args = []
    if len(args) != 2:
        print >>sys.stderr, usage
        return -1
    options = dict(optlist)

    charset = options.get('c') or 'utf-8'
    template = options.get('t') or 'werkzeug_default'
    package, dst = args

    return bootstrap(package, dst, template, charset)
