import atexit
import shutil
from werkzeug.contrib.sessions import FilesystemSessionStore
from tempfile import mkdtemp, gettempdir


session_folder = mkdtemp()
atexit.register(lambda: shutil.rmtree(session_folder))


def test_default_tempdir():
    """Ensure that sessions go to the tempdir by default"""
    store = FilesystemSessionStore()
    assert store.path == gettempdir()


def test_basic_fs_sessions():
    """Test basic file system sessions"""
    store = FilesystemSessionStore(session_folder)
    x = store.new()
    assert x.new
    assert not x.modified
    x['foo'] = [1, 2, 3]
    assert x.modified
    store.save(x)

    x2 = store.get(x.sid)
    assert not x2.new
    assert not x2.modified
    assert x2 is not x
    assert x2 == x
    x2['test'] = 3
    assert x2.modified
    assert not x2.new
    store.save(x2)

    x = store.get(x.sid)
    store.delete(x)
    x2 = store.get(x.sid)
    # the session is not new when it was used previously.
    assert not x2.new


def test_renewing_fs_session():
    """Test renewing file system sessions"""
    store = FilesystemSessionStore(session_folder, renew_missing=True)
    x = store.new()
    store.save(x)
    store.delete(x)
    x2 = store.get(x.sid)
    assert x2.new


def test_fs_session_lising():
    """Test listing of filesystem sessions"""
    store = FilesystemSessionStore(session_folder, renew_missing=True)
    sessions = set()
    for x in xrange(10):
        sess = store.new()
        store.save(sess)
        sessions.add(sess.sid)

    listed_sessions = set(store.list())
    assert sessions == listed_sessions
