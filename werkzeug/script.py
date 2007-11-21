# -*- coding: utf-8 -*-
"""
    werkzeug.script
    ~~~~~~~~~~~~~~~

    This module provides classes that simplifies the creation of shell
    scripts.  The `Script` class is very basic and does not contain any
    default actions.  The `ManagementScript` class however includes some
    common actions such as running a WSGI server and starting a python
    shell.


    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import sys
import inspect
import getopt


argument_types = {
    bool:       'boolean',
    str:        'string',
    int:        'integer',
    float:      'float'
}


converters = {
    'boolean':  lambda x: x.lower() in ('1', 'true', 'yes', 'on'),
    'string':   str,
    'integer':  int,
    'float':    float
}


def run(frame_offset=0):
    """
    Run the script.  Participating actions are looked up in the callers
    namespace.
    """
    frm = sys._getframe(1 + max(0, frame_offset))
    actions = {}
    for key, value in frm.f_locals.iteritems():
        if key.startswith('action_'):
            actions[key[7:]] = analyse_action(value)

    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        return print_usage(actions)
    elif args[0] not in actions:
        fail('Unknown action \'%s\'' % args[0])

    arguments = {}
    conv = {}
    key_to_arg = {}
    long_options = []
    formatstring = ''
    func, doc, arg_def = actions[args.pop(0)]
    for arg, shortcut, default, option_type in arg_def:
        real_arg = arg.replace('-', '_')
        converter = converters[option_type]
        if shortcut:
            formatstring += shortcut + ':'
            key_to_arg['-' + shortcut] = real_arg
            conv['-' + shortcut] = converter
        long_options.append(arg + '=')
        key_to_arg['--' + arg] = real_arg
        conv['--' + arg] = converter
        arguments[real_arg] = default

    try:
        optlist, args = getopt.gnu_getopt(args, formatstring, long_options)
    except getopt.GetoptError, e:
        fail(str(e))

    for key, value in optlist:
        try:
            arguments[key_to_arg[key]] = conv[key](value)
        except ValueError:
            fail('Invalid value for \'%s\': %s' % (key, value))

    return func(**arguments)


def fail(message, code=-1):
    """Fail with an error."""
    print >> sys.stderr, 'Error:', message
    sys.exit(code)


def print_usage(actions):
    """Print the usage information.  (Help screen)"""
    actions = actions.items()
    actions.sort()
    print 'usage: %s <action> [<options>]' % sys.argv[0]
    print '       %s --help' % sys.argv[0]
    print
    print 'actions:'
    for name, (func, doc, arguments) in actions:
        print '  %s:' % name
        for line in doc.splitlines():
            print '    %s' % line
        if arguments:
            print
        for arg, shortcut, default, type in arguments:
            print '    %-30s%-10s%s' % (
                (shortcut and '-%s, ' % shortcut or '') + '--' + arg,
                type,
                default
            )
        print


def analyse_action(func):
    """Analyse a function."""
    description = inspect.getdoc(func)
    arguments = []
    args, varargs, kwargs, defaults = inspect.getargspec(func)
    if varargs or kwargs:
        raise TypeError('variable length arguments for action not allowed.')
    if len(args) != len(defaults or ()):
        raise TypeError('not all arguments have proper definitions')

    for idx, (arg, definition) in enumerate(zip(args, defaults or ())):
        if arg.startswith('_'):
            raise TypeError('arguments may not start with an underscore')
        if not isinstance(definition, tuple):
            shortcut = None
            default = definition
        else:
            shortcut, default = definition
        argument_type = argument_types[type(default)]
        arguments.append((arg.replace('_', '-'), shortcut,
                          default, argument_type))
    return func, description, arguments


def make_shell(init_func=lambda: {}, banner=None, use_ipython=True):
    """
    Returns an action callback that spawns a new interactive
    python shell.
    """
    if banner is None:
        banner = 'Interactive Werkzeug Shell'
    def action(use_ipython=use_ipython):
        """Start a new interactive python session."""
        namespace = init_func()
        if use_ipython:
            try:
                import IPython
            except ImportError:
                pass
            else:
                sh = IPython.Shell.IPShellEmbed(banner=banner)
                sh(global_ns={}, local_ns=namespace)
                return
        from code import interact
        interact(banner, local=namespace)
    return action


def make_runserver(app_factory, hostname='localhost', port=5000,
                   use_reloader=False, threaded=False, processes=1):
    """
    Returns an action callback that spawns a new wsgiref server.
    """
    def action(hostname=('h', hostname), port=('p', port),
               use_reloader=use_reloader, threaded=threaded,
               processes=processes):
        """Start a new development server."""
        from werkzeug.serving import run_simple
        run_simple(hostname, port, app_factory(), use_reloader,
                   None, threaded, processes)
    return action
