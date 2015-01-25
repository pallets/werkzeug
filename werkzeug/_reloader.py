import os
import sys
import time
import subprocess
import threading
from itertools import chain

from werkzeug._internal import _log
from werkzeug._compat import PY2, iteritems, text_type


def _iter_module_files():
    """This iterates over all relevant Python files.  It goes through all
    loaded files from modules, all files in folders of already loaded modules
    as well as all files reachable through a package.
    """
    found = set()
    entered = set()

    def _verify_file(filename):
        if not filename:
            return
        filename = os.path.abspath(filename)
        old = None
        while not os.path.isfile(filename):
            old = filename
            filename = os.path.dirname(filename)
            if filename == old:
                break
        else:
            if filename[-4:] in ('.pyc', '.pyo'):
                filename = filename[:-1]
            if filename not in found:
                found.add(filename)
                return filename

    def _recursive_walk(path_entry):
        if path_entry in entered:
            return
        entered.add(path_entry)
        try:
            for filename in os.listdir(path_entry):
                path = os.path.join(path_entry, filename)
                if os.path.isdir(path):
                    for filename in _recursive_walk(path):
                        yield filename
                else:
                    if not filename.endswith(('.py', '.pyc', '.pyo')):
                        continue
                    filename = _verify_file(path)
                    if filename:
                        yield filename
        except OSError:
            pass

    # The list call is necessary on Python 3 in case the module
    # dictionary modifies during iteration.
    for path_entry in list(sys.path):
        for filename in _recursive_walk(os.path.abspath(path_entry)):
            yield filename

    for module in list(sys.modules.values()):
        if module is None:
            continue
        filename = _verify_file(getattr(module, '__file__', None))
        if filename:
            yield filename
            for filename in _recursive_walk(os.path.dirname(filename)):
                yield filename
        for package_path in getattr(module, '__path__', ()):
            for filename in _recursive_walk(os.path.abspath(package_path)):
                yield filename


def _find_observable_paths(extra_files=None):
    """Finds all paths that should be observed."""
    rv = set(os.path.abspath(x) for x in sys.path)
    for filename in extra_files or ():
        rv.append(os.path.dirname(os.path.abspath(filename)))
    for module in list(sys.modules.values()):
        fn = getattr(module, '__file__', None)
        if fn is None:
            continue
        fn = os.path.abspath(fn)
        rv.add(os.path.dirname(fn))
    return rv


def _find_common_roots(paths):
    """Out of some paths it finds the common roots that need monitoring."""
    paths = [x.split(os.path.sep) for x in paths]
    root = {}
    for chunks in sorted(paths, key=len, reverse=True):
        node = root
        for chunk in chunks:
            node = node.setdefault(chunk, {})
        node.clear()

    rv = set()
    def _walk(node, path):
        for prefix, child in iteritems(node):
            _walk(child, path + (prefix,))
        if not node:
            rv.add('/'.join(path))
    _walk(root, ())
    return rv


class ReloaderLoop(object):
    _sleep = time.sleep  # monkeypatched by testsuite
    name = None

    def __init__(self, extra_files=None, interval=1):
        self.extra_files = set(os.path.abspath(x)
                               for x in extra_files or ())
        self.interval = interval

    def run(self):
        pass

    def restart_with_reloader(self):
        """Spawn a new Python interpreter with the same arguments as this one,
        but running the reloader thread.
        """
        while 1:
            _log('info', ' * Restarting with %s' % self.name)
            args = [sys.executable] + sys.argv
            new_environ = os.environ.copy()
            new_environ['WERKZEUG_RUN_MAIN'] = 'true'

            # a weird bug on windows. sometimes unicode strings end up in the
            # environment and subprocess.call does not like this, encode them
            # to latin1 and continue.
            if os.name == 'nt' and PY2:
                for key, value in iteritems(new_environ):
                    if isinstance(value, text_type):
                        new_environ[key] = value.encode('iso-8859-1')

            exit_code = subprocess.call(args, env=new_environ)
            if exit_code != 3:
                return exit_code

    def trigger_reload(self, filename):
        filename = os.path.abspath(filename)
        _log('info', ' * Detected change in %r, reloading' % filename)
        sys.exit(3)


class StatReloaderLoop(ReloaderLoop):
    name = 'stat'

    def run(self):
        mtimes = {}
        while 1:
            for filename in chain(_iter_module_files(), self.extra_files):
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue

                old_time = mtimes.get(filename)
                if old_time is None:
                    mtimes[filename] = mtime
                    continue
                elif mtime > old_time:
                    self.trigger_reload(filename)
            self._sleep(self.interval)


class WatchdogReloaderLoop(ReloaderLoop):

    def __init__(self, *args, **kwargs):
        ReloaderLoop.__init__(self, *args, **kwargs)
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        self.observable_paths = set()

        def _check_modification(filename):
            if filename in self.extra_files:
                self.trigger_reload(filename)
            dirname = os.path.dirname(filename)
            if dirname.startswith(tuple(self.observable_paths)):
                if filename.endswith(('.pyc', '.pyo')):
                    self.trigger_reload(filename[:-1])
                elif filename.endswith('.py'):
                    self.trigger_reload(filename)

        class _CustomHandler(FileSystemEventHandler):
            def on_created(self, event):
                _check_modification(event.src_path)
            def on_modified(self, event):
                _check_modification(event.src_path)

        reloader_name = Observer.__name__.lower()
        if reloader_name.endswith('observer'):
            reloader_name = reloader_name[:-8]
        reloader_name += ' reloader'

        self.name = reloader_name

        self.observer_class = Observer
        self.event_handler = _CustomHandler()
        self.should_reload = False

    def trigger_reload(self, filename):
        # This is called inside an event handler, which means we can't throw
        # SystemExit here. https://github.com/gorakhargosh/watchdog/issues/294
        self.should_reload = True
        ReloaderLoop.trigger_reload(self, filename)

    def run(self):
        watches = {}
        observer = self.observer_class()
        observer.start()

        while not self.should_reload:
            to_delete = set(watches)
            paths = _find_common_roots(
                _find_observable_paths(self.extra_files))
            for path in paths:
                if path not in watches:
                    try:
                        watches[path] = observer.schedule(
                            self.event_handler, path, recursive=True)
                    except OSError:
                        # "Path is not a directory". We could filter out
                        # those paths beforehand, but that would cause
                        # additional stat calls.
                        watches[path] = None
                to_delete.discard(path)
            for path in to_delete:
                watch = watches.pop(path, None)
                if watch is not None:
                    observer.unschedule(watch)
            self.observable_paths = paths
            self._sleep(self.interval)

        sys.exit(3)


reloader_loops = {
    'stat': StatReloaderLoop,
    'watchdog': WatchdogReloaderLoop,
}

try:
    __import__('watchdog.observers')
except ImportError:
    reloader_loops['auto'] = reloader_loops['stat']
else:
    reloader_loops['auto'] = reloader_loops['watchdog']


def run_with_reloader(main_func, extra_files=None, interval=1,
                      reloader_type='auto'):
    """Run the given function in an independent python interpreter."""
    import signal
    reloader = reloader_loops[reloader_type](extra_files, interval)
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    try:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            t = threading.Thread(target=main_func, args=())
            t.setDaemon(True)
            t.start()
            reloader.run()
        else:
            sys.exit(reloader.restart_with_reloader())
    except KeyboardInterrupt:
        pass
