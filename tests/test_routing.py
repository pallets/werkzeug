# -*- coding: utf-8 -*-
"""
    werkzeug.routing test
    ~~~~~~~~~~~~~~~~~~~~~


    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
from nose.tools import assert_raises

from werkzeug.wrappers import Response
from werkzeug.routing import Map, Rule, NotFound, BuildError, RequestRedirect
from werkzeug.test import create_environ


def test_basic_routing():
    """Basic URL routing"""
    map = Map([
        Rule('/', endpoint='index'),
        Rule('/foo', endpoint='foo'),
        Rule('/bar/', endpoint='bar')
    ])
    adapter = map.bind('example.org', '/')
    assert adapter.match('/') == ('index', {})
    assert adapter.match('/foo') == ('foo', {})
    assert adapter.match('/bar/') == ('bar', {})
    assert_raises(RequestRedirect, lambda: adapter.match('/bar'))
    assert_raises(NotFound, lambda: adapter.match('/blub'))


test_environ_defaults = '''
>>> from werkzeug.routing import Map, Rule
>>> from werkzeug import create_environ
>>> environ = create_environ("/foo")
>>> environ["PATH_INFO"]
'/foo'
>>> m = Map([Rule("/foo", endpoint="foo"), Rule("/bar", endpoint="bar")])
>>> a = m.bind_to_environ(environ)
>>> a.match("/foo")
('foo', {})
>>> a.match()
('foo', {})
>>> a.match("/bar")
('bar', {})
>>> a.match("/bars")
Traceback (most recent call last):
  ...
NotFound: 404 Not Found
'''


def test_basic_building():
    """Basic URL building"""
    map = Map([
        Rule('/', endpoint='index'),
        Rule('/foo', endpoint='foo'),
        Rule('/bar/<baz>', endpoint='bar'),
        Rule('/bar/<int:bazi>', endpoint='bari'),
        Rule('/bar/<float:bazf>', endpoint='barf'),
        Rule('/bar/<path:bazp>', endpoint='barp'),
        Rule('/hehe', endpoint='blah', subdomain='blah')
    ])
    adapter = map.bind('example.org', '/', subdomain='blah')

    assert adapter.build('index', {}) == 'http://example.org/'
    assert adapter.build('foo', {}) == 'http://example.org/foo'
    assert adapter.build('bar', {'baz': 'blub'}) == 'http://example.org/bar/blub'
    assert adapter.build('bari', {'bazi': 50}) == 'http://example.org/bar/50'
    assert adapter.build('barf', {'bazf': 0.815}) == 'http://example.org/bar/0.815'
    assert adapter.build('barp', {'bazp': 'la/di'}) == 'http://example.org/bar/la/di'
    assert adapter.build('blah', {}) == '/hehe'
    assert_raises(BuildError, lambda: adapter.build('urks'))


def test_defaults():
    """URL routing defaults"""
    map = Map([
        Rule('/foo/', defaults={'page': 1}, endpoint='foo'),
        Rule('/foo/<int:page>', endpoint='foo')
    ])
    adapter = map.bind('example.org', '/')

    assert adapter.match('/foo/') == ('foo', {'page': 1})
    assert_raises(RequestRedirect, lambda: adapter.match('/foo/1'))
    assert adapter.match('/foo/2') == ('foo', {'page': 2})
    assert adapter.build('foo', {}) == '/foo/'
    assert adapter.build('foo', {'page': 1}) == '/foo/'
    assert adapter.build('foo', {'page': 2}) == '/foo/2'


def test_greedy():
    """URL routing greedy settings"""
    map = Map([
        Rule('/foo', endpoint='foo'),
        Rule('/<path:bar>', endpoint='bar'),
        Rule('/<path:bar>/<path:blub>', endpoint='bar')
    ])
    adapter = map.bind('example.org', '/')

    assert adapter.match('/foo') == ('foo', {})
    assert adapter.match('/blub') == ('bar', {'bar': 'blub'})
    assert adapter.match('/he/he') == ('bar', {'bar': 'he', 'blub': 'he'})

    assert adapter.build('foo', {}) == '/foo'
    assert adapter.build('bar', {'bar': 'blub'}) == '/blub'
    assert adapter.build('bar', {'bar': 'blub', 'blub': 'bar'}) == '/blub/bar'


def test_path():
    """URL routing path converter behavior"""
    map = Map([
        Rule('/', defaults={'name': 'FrontPage'}, endpoint='page'),
        Rule('/Special', endpoint='special'),
        Rule('/<int:year>', endpoint='year'),
        Rule('/<path:name>', endpoint='page'),
        Rule('/<path:name>/edit', endpoint='editpage'),
        Rule('/<path:name>/silly/<path:name2>', endpoint='sillypage'),
        Rule('/<path:name>/silly/<path:name2>/edit', endpoint='editsillypage'),
        Rule('/Talk:<path:name>', endpoint='talk'),
        Rule('/User:<username>', endpoint='user'),
        Rule('/User:<username>/<path:name>', endpoint='userpage'),
        Rule('/Files/<path:file>', endpoint='files'),
    ])
    adapter = map.bind('example.org', '/')

    assert adapter.match('/') == ('page', {'name':'FrontPage'})
    assert_raises(RequestRedirect, lambda: adapter.match('/FrontPage'))
    assert adapter.match('/Special') == ('special', {})
    assert adapter.match('/2007') == ('year', {'year':2007})
    assert adapter.match('/Some/Page') == ('page', {'name':'Some/Page'})
    assert adapter.match('/Some/Page/edit') == ('editpage', {'name':'Some/Page'})
    assert adapter.match('/Foo/silly/bar') == ('sillypage', {'name':'Foo', 'name2':'bar'})
    assert adapter.match('/Foo/silly/bar/edit') == ('editsillypage', {'name':'Foo', 'name2':'bar'})
    assert adapter.match('/Talk:Foo/Bar') == ('talk', {'name':'Foo/Bar'})
    assert adapter.match('/User:thomas') == ('user', {'username':'thomas'})
    assert adapter.match('/User:thomas/projects/werkzeug') == ('userpage', {'username':'thomas', 'name':'projects/werkzeug'})
    assert adapter.match('/Files/downloads/werkzeug/0.2.zip') == ('files', {'file':'downloads/werkzeug/0.2.zip'})


def test_dispatch():
    """URL routing dispatch helper"""
    env = create_environ('/')
    map = Map([
        Rule('/', endpoint='root'),
        Rule('/foo/', endpoint='foo')
    ])
    adapter = map.bind_to_environ(env)

    raise_this = None
    def view_func(endpoint, values):
        if raise_this is not None:
            raise raise_this
        return Response(repr((endpoint, values)))
    dispatch = lambda p, q=False: Response.force_type(adapter.dispatch(view_func, p,
                                                      catch_http_exceptions=q), env)

    assert dispatch('/').data == "('root', {})"
    assert dispatch('/foo').status_code == 301
    raise_this = NotFound()
    assert_raises(NotFound, lambda: dispatch('/bar'))
    assert dispatch('/bar', True).status_code == 404


def test_http_host_before_server_name():
    """URL routing HTTP host takes precedence before server name"""
    env = {
        'HTTP_HOST':            'wiki.example.com',
        'SERVER_NAME':          'web0.example.com',
        'SERVER_PORT':          '80',
        'SCRIPT_NAME':          '',
        'PATH_INFO':            '',
        'REQUEST_METHOD':       'GET',
        'wsgi.url_scheme':      'http'
    }
    map = Map([Rule('/', endpoint='index', subdomain='wiki')])
    adapter = map.bind_to_environ(env, server_name='example.com')
    assert adapter.match('/') == ('index', {})
    assert adapter.build('index', force_external=True) == 'http://wiki.example.com/'
    assert adapter.build('index') == '/'

    env['HTTP_HOST'] = 'admin.example.com'
    adapter = map.bind_to_environ(env, server_name='example.com')
    assert adapter.build('index') == 'http://wiki.example.com/'


def test_adapter_url_parameter_sorting():
    """Optional adapter URL parameter sorting"""
    map = Map([Rule('/', endpoint='index')], sort_parameters=True,
              sort_key=lambda x: x[1])
    adapter = map.bind('localhost', '/')
    assert adapter.build('index', {'x': 20, 'y': 10, 'z': 30},
        force_external=True) == 'http://localhost/?y=10&x=20&z=30'


def test_request_direct_charset_bug():
    map = Map([Rule(u'/öäü/')])
    adapter = map.bind('localhost', '/')
    try:
        adapter.match(u'/öäü')
    except RequestRedirect, e:
        print repr(e.new_url)
        assert e.new_url == 'http://localhost/%C3%B6%C3%A4%C3%BC/'
    else:
        raise AssertionError('expected request redirect exception')

def test_adapter_match_return_rule():
    """Returning the matched Rule"""
    rule = Rule('/foo/', endpoint='foo')
    map = Map([rule])
    adapter = map.bind('localhost', '/')
    assert adapter.match('/foo/', return_rule=True) == (rule, {})


def test_server_name_interpolation():
    """URL routing server name interpolation."""
    server_name = 'example.invalid'
    map = Map([Rule('/', endpoint='index'),
               Rule('/', endpoint='alt', subdomain='alt')])

    env = create_environ('/', 'http://%s/' % server_name)
    adapter = map.bind_to_environ(env, server_name=server_name)
    assert adapter.match() == ('index', {})

    env = create_environ('/', 'http://alt.%s/' % server_name)
    adapter = map.bind_to_environ(env, server_name=server_name)
    assert adapter.match() == ('alt', {})

    try:
        env = create_environ('/', 'http://%s/' % server_name)
        adapter = map.bind_to_environ(env, server_name='foo')
    except ValueError, e:
        msg = str(e)
        assert 'provided (%r)' % 'foo' in msg
        assert 'environment (%r)' % server_name in msg
    else:
        assert False, 'expected exception'
