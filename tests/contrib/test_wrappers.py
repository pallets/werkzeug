from werkzeug.contrib import wrappers
from werkzeug import Request, routing


def test_reverse_slash_behavior():
    """Test ReverseSlashBehaviorRequestMixin"""
    class MyRequest(wrappers.ReverseSlashBehaviorRequestMixin, Request):
        pass
    req = MyRequest.from_values('/foo/bar', 'http://example.com/test')
    assert req.url == 'http://example.com/test/foo/bar'
    assert req.path == 'foo/bar'
    assert req.script_root == '/test/'
    assert req.peek_path_info() == 'foo'
    assert req.pop_path_info() == 'foo'
    assert req.path == 'bar'
    assert req.script_root == '/test/foo/'

    # make sure the routing system works with the slashes in
    # reverse order as well.
    map = routing.Map([routing.Rule('/bar', endpoint='foo')])
    adapter = map.bind_to_environ(req.environ)
    assert adapter.match() == ('foo', {})
    adapter = map.bind(req.host, req.script_root)
    assert adapter.match(req.path) == ('foo', {})
