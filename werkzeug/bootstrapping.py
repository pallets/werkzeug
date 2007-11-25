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
from getopt import getopt, GetoptError
from werkzeug.templates import Template


TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')

par_re = re.compile(r'\n{2,}')


def make_textblock(left, right, text):
    """
    Helper function to indent some text. This is usually used by the
    docstring template.
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
    if os.path.exists(template):
        template_path = template
    else:
        template_path = os.path.join(TEMPLATES, template)
    if not os.path.exists(template_path):
        print >>sys.stderr, 'Template "%s" not found' % \
                            os.path.basename(template_path)
        return -2
    template_path = os.path.abspath(template_path)

    # the pascal cased name of the package is used in the
    # templates for creating class names etc.
    pascal_cased = package_name.title().replace('_', '')
    print 'Generating from "%s"' % template_path

    # if someone want's to use the `make_docstring` function there
    # should be a template for all of the docstrings (``.DOCSTRING``)
    filename = os.path.join(template_path, '.DOCSTRING')
    if os.path.exists(filename):
        docstring_template = Template.from_file(filename)
    else:
        docstring_template = Template('$DOCSTRING')

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

                # process templated files
                if src_fn.endswith('_tmpl'):
                    dst_fn = dst_fn[:-5]
                    tmpl = Template(data.decode('utf-8'), src_fn)
                    ctx = get_context(dst_fn[len(destination_path) + 1:])
                    data = tmpl.render(ctx).encode(charset)

                f = file(dst_fn, 'wb')
                try:
                    f.write(data)
                finally:
                    f.close()

                print '   ' + dst_fn[len(destination_path) + 1:]

            # for each folder recursive and create a new one in the
            # target location. We don't ignore empty folders.
            elif os.path.isdir(src_fn):
                try:
                    os.mkdir(dst_fn)
                except OSError:
                    pass
                walk(src_fn)

    walk(template_path)

    # after processing the templates we look for a ``.INFO`` file
    # that can contain some post processing information. If it
    # doesn't exist we fall back to a simple "Finished template generation".
    info_fn = os.path.join(template_path, '.INFO')
    if os.path.exists(info_fn):
        tmpl = Template.from_file(info_fn)
        f = file(info_fn)
        try:
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

    version = '''werkzeug-bootstrap - werkzeug 0.1

    Copyright (C) 2007 The Pocoo Team.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

      * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.

      * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.

      * The name of the author may not be used to endorse or promote products
      derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE AS AND ANY EXPRESS OR IMPLIED WARRANTIES,
    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
    OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

    Written by The Pocoo Team.'''

    help = '''Usage: %s [OPTION] DIRECTORY

    The %s command generates bootstrapping code from templates in the DIRECTORY.

    The exit status is 0 for success or -1 for failure.

    Options:

      -h, --help      Display a short help message and exit.
      -v, --version   Display version information and exit.
      -t, --template  Project template to use.
      -c, --charset   Character set used for the files and application.
      -a, --author    Project author\'s name.

    Report bugs via the web at <http://dev.pocoo.org/projects/werkzeug>.''' % (
        os.path.basename(args[0]), os.path.basename(args[0]))

    try:
        optlist, args = getopt(args[1:], 'vht:c:a:',
            ['version', 'help', 'template=', 'charset=', 'author='])
    except GetoptError, err:
        args = []
    options = dict(optlist)
    if '--version' in options:
        print >>sys.stdout, re.sub('\n    ', '\n', version)
        return -1
    if '--help' in options:
        print >>sys.stdout, re.sub('\n    ', '\n', help)
        return -1
    if len(args) not in (1, 2):
        print >>sys.stderr, re.sub('\n    ', '\n', help)
        return -1

    charset = options.get('-c') or options.get('--charset') or 'utf-8'
    template = options.get('-t') or options.get('--template') or 'default'
    author = options.get('-a') or options.get('--author')
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
