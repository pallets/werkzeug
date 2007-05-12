# -*- coding: utf-8 -*-
"""
    werkzeug.bootstrapping
    ~~~~~~~~~~~~~~~~~~~~~~

    Module that contains some code that is able to create new
    python packages based on templates.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
import sys
import textwrap
from datetime import datetime
from fnmatch import fnmatch
from getopt import getopt, GetoptError
from werkzeug.minitmpl import Template


TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATED_FILTERS = ['*.py', '*.html', '*.txt']

par_re = re.compile(r'\n{2,}')


def make_textblock(left, right, text):
    """
    Helper function to indent some text. This is used by the
    `make_docstring` function available in the context of a
    file template.
    """
    return u'\n\n'.join([textwrap.fill(block, right - left,
                                       initial_indent=' ' * left,
                                       subsequent_indent=' ' * left)
                         for block in par_re.split(text)])


def bootstrap(package_name, destination_path, template, charset, author):
    """
    Perform the bootstrapping.
    """
    # if we have an template path we load the templates located there
    # otherwise we load the templates from the template folder.
    if os.sep in template:
        template_path = template
    else:
        template_path = os.path.join(TEMPLATES, template)
    if not os.path.exists(template_path):
        print >>sys.stderr, "Template path not found"
        return -2

    # the pascal cased name of the package is used in the
    # templates for creating class names etc.
    pascal_cased = package_name.title().replace('_', '')
    print 'Generating from "%s"' % template_path

    # all template packages can have a ``.TEMPLATED`` control file
    # that contains fnmatch rules which are used to tell the bootstrapping
    # loop which files are templates and which aren't.
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

    # if someone want's to use the `make_docstring` function there
    # should be a template for all of the docstrings (``.DOCSTRING``)
    try:
        f = file(os.path.join(template_path, '.DOCSTRING'))
    except IOError:
        docstring_template = '<%= DOCSTRING %>'
    else:
        try:
            docstring_template = f.read().decode('utf-8')
        finally:
            f.close()
    docstring_template = Template(docstring_template)

    # create the target folder if it does not exist by now.
    try:
        os.makedirs(destination_path)
    except OSError:
        pass

    def docstring_helper(module, text):
        """Helper function that creates a docstring based
        on the template in ``.DOCSTRING``."""
        ctx = base_context.copy()
        ctx.update(
            MODULE=module,
            DOCSTRING=text
        )
        return docstring_template.render(ctx)

    def get_context(filename):
        """Helper function that creates a template context
        for a given filename. Depending on the file extension
        more or less items will appear in the context."""
        rv = base_context.copy()
        if filename.endswith('.py'):
            if filename.endswith(os.sep + '__init__.py'):
                filename = filename[:-12]
            else:
                filename = filename[:-3]
            rv['MODULE'] = filename.replace(os.sep, '.')
        return rv

    # assamble the base context. this is done here so that
    # we don't have to do that for each file.
    base_context = dict(
        PACKAGE=package_name,
        PACKAGE_PASCAL_CASED=pascal_cased,
        FILE_ENCODING=charset,
        AUTHOR=author,
        make_textblock=make_textblock,
        make_docstring=docstring_helper,
        datetime=datetime
    )

    def walk(p):
        """
        Helper function that is called recursive for each file in
        the template directory. It renders templates and creates folders.
        """
        for fn in os.listdir(p):
            # names that start with a dot are ignored
            if fn.startswith('.'):
                continue

            src_fn = os.path.join(p, fn)
            dst_fn = os.path.join(destination_path, p[len(template_path)
                                  + 1:], fn).replace('PACKAGE', package_name)

            # files get template threatment if wanted, otherwise they
            # are copied from the source to the target location.
            if os.path.isfile(src_fn):
                f = file(src_fn)
                try:
                    data = f.read()
                finally:
                    f.close()

                for pat in templated_filters:
                    # templated files are encoded to the target encoding,
                    # other files (because they could be binary) are just
                    # copied as it.
                    if fnmatch(src_fn, pat):
                        tmpl = Template(data.decode('utf-8'))
                        ctx = get_context(dst_fn[len(destination_path) + 1:])
                        data = tmpl.render(ctx).encode(charset)
                        break

                f = file(dst_fn, 'wb')
                try:
                    f.write(data)
                finally:
                    f.close()

                print '   ' + dst_fn

            # for each folder recursive and create a new one in the
            # target location. We don't ignore empty folders.
            elif os.path.isdir(src_fn):
                os.mkdir(dst_fn)
                walk(src_fn)

    walk(template_path)

    # after processing the templates we look for a ``.INFO`` file
    # that can contain some post processing information. If it
    # doesn't exist we fall back to a simple "Finished template generation".
    info_fn = os.path.join(template_path, '.INFO')
    if os.path.exists(info_fn):
        f = file(info_fn)
        try:
            tmpl = Template(f.read().decode('utf-8'))
            ctx = get_context('.INFO')
            msg = tmpl.render(ctx).encode(sys.stdout.encoding, 'ignore')
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
    usage = 'Usage: %s [-t <template>] [-c <charset>] [-a <author>] ' \
            '<package> <dst>' % os.path.basename(args[0])
    try:
        optlist, args = getopt(args[1:], 't:c:a:')
    except GetoptError, err:
        args = []
    if len(args) not in (1, 2):
        print >>sys.stderr, usage
        return -1
    options = dict(optlist)

    charset = options.get('-c') or 'utf-8'
    template = options.get('-t') or 'werkzeug_default'
    author = options.get('-a')
    if not author:
        from getpass import getuser
        author = getuser()
        try:
            import pwd
            author = pwd.getpwnam(author)[4].split(',')[0]
        except:
            pass
    package = args.pop(0)
    dst = args and args[0] or '.'

    return bootstrap(package, dst, template, charset, author)
