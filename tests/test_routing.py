# -*- coding: utf-8 -*-
"""
    werkzeug.routing test
    ~~~~~~~~~~~~~~~~~~~~~


    :copyright: 2007 by Armin Ronacher.
    :license: BSD license.
"""
from py.test import raises
from werkzeug.routing import Map, Rule, NotFound, BuildError, RequestRedirect
from werkzeug.utils import create_environ


def test_basic_routing():
    map = Map([
        Rule('/', endpoint='index'),
        Rule('/foo', endpoint='foo'),
        Rule('/bar/', endpoint='bar')
    ])
    adapter = map.bind('example.org', '/')
    assert adapter.match('/') == ('index', {})
    assert adapter.match('/foo') == ('foo', {})
    assert adapter.match('/bar/') == ('bar', {})
    raises(RequestRedirect, lambda: adapter.match('/bar'))
    raises(NotFound, lambda: adapter.match('/blub'))


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
    raises(BuildError, lambda: adapter.build('urks'))


def test_defaults():
    map = Map([
        Rule('/foo/', defaults={'page': 1}, endpoint='foo'),
        Rule('/foo/<int:page>', endpoint='foo')
    ])
    adapter = map.bind('example.org', '/')

    assert adapter.match('/foo/') == ('foo', {'page': 1})
    raises(RequestRedirect, lambda: adapter.match('/foo/1'))
    assert adapter.match('/foo/2') == ('foo', {'page': 2})
    assert adapter.build('foo', {}) == '/foo/'
    assert adapter.build('foo', {'page': 1}) == '/foo/'
    assert adapter.build('foo', {'page': 2}) == '/foo/2'


def test_greedy():
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
    raises(RequestRedirect, lambda: adapter.match('/FrontPage'))
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
