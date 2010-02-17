# -*- coding: utf-8 -*-
"""
    werkzeug.utils test
    ~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import sys
from datetime import datetime
from StringIO import StringIO

from nose.tools import assert_raises

from werkzeug.utils import *
from werkzeug.wrappers import BaseResponse, Request
from werkzeug.http import parse_date
from werkzeug.test import Client, run_wsgi_app, create_environ


def test_import_patch():
    """Import patch"""
    import werkzeug
    from werkzeug import __all__ as public_methods
    for name in public_methods:
        getattr(werkzeug, name)


def test_cached_property():
    """Cached property decorator"""
    foo = []
    class A(object):
        def prop(self):
            foo.append(42)
            return 42
        prop = cached_property(prop)

    a = A()
    p = a.prop
    q = a.prop
    assert p == q == 42
    assert foo == [42]

    foo = []
    class A(object):
        def _prop(self):
            foo.append(42)
            return 42
        prop = cached_property(_prop, name='prop')
        del _prop

    a = A()
    p = a.prop
    q = a.prop
    assert p == q == 42
    assert foo == [42]


def test_environ_property():
    """Environ property descriptor"""
    class A(object):
        environ = {'string': 'abc', 'number': '42'}

        string = environ_property('string')
        missing = environ_property('missing', 'spam')
        read_only = environ_property('number')
        number = environ_property('number', load_func=int)
        broken_number = environ_property('broken_number', load_func=int)
        date = environ_property('date', None, parse_date, http_date,
                                read_only=False)
        foo = environ_property('foo')

    a = A()
    assert a.string == 'abc'
    assert a.missing == 'spam'
    def test_assign():
        a.read_only = 'something'
    assert_raises(AttributeError, test_assign)
    assert a.number == 42
    assert a.broken_number == None
    assert a.date is None
    a.date = datetime(2008, 1, 22, 10, 0, 0, 0)
    assert a.environ['date'] == 'Tue, 22 Jan 2008 10:00:00 GMT'


def test_escape():
    """XML/HTML escaping"""
    class Foo(str):
        def __html__(self):
            return unicode(self)
    assert escape(None) == ''
    assert escape(42) == '42'
    assert escape('<>') == '&lt;&gt;'
    assert escape('"foo"') == '"foo"'
    assert escape('"foo"', True) == '&quot;foo&quot;'
    assert escape(Foo('<foo>')) == '<foo>'


def test_unescape():
    """XML/HTML unescaping"""
    assert unescape('&lt;&auml;&gt;') == u'<ä>'


def test_run_wsgi_app():
    """WSGI test-runner"""
    def foo(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield '1'
        yield '2'
        yield '3'

    app_iter, status, headers = run_wsgi_app(foo, {})
    assert status == '200 OK'
    assert headers == [('Content-Type', 'text/plain')]
    assert app_iter.next() == '1'
    assert app_iter.next() == '2'
    assert app_iter.next() == '3'
    assert_raises(StopIteration, app_iter.next)

    got_close = []
    class CloseIter(object):
        def __init__(self):
            self.iterated = False
        def __iter__(self):
            return self
        def close(self):
            got_close.append(None)
        def next(self):
            if self.iterated:
                raise StopIteration()
            self.iterated = True
            return 'bar'

    def bar(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return CloseIter()

    app_iter, status, headers = run_wsgi_app(bar, {})
    assert status == '200 OK'
    assert headers == [('Content-Type', 'text/plain')]
    assert app_iter.next() == 'bar'
    assert_raises(StopIteration, app_iter.next)
    app_iter.close()

    assert run_wsgi_app(bar, {}, True)[0] == ['bar']

    assert len(got_close) == 2


def test_dates():
    """Date formatting"""
    assert cookie_date(0) == 'Thu, 01-Jan-1970 00:00:00 GMT'
    assert cookie_date(datetime(1970, 1, 1)) == 'Thu, 01-Jan-1970 00:00:00 GMT'
    assert http_date(0) == 'Thu, 01 Jan 1970 00:00:00 GMT'
    assert http_date(datetime(1970, 1, 1)) == 'Thu, 01 Jan 1970 00:00:00 GMT'


def test_cookies():
    """Cookie parsing"""
    assert parse_cookie('dismiss-top=6; CP=null*; PHPSESSID=0a539d42abc001cd'
                        'c762809248d4beed; a=42') == {
        'CP':           u'null*',
        'PHPSESSID':    u'0a539d42abc001cdc762809248d4beed',
        'a':            u'42',
        'dismiss-top':  u'6'
    }
    assert set(dump_cookie('foo', 'bar baz blub', 360, httponly=True,
                           sync_expires=False).split('; ')) == \
           set(['HttpOnly', 'Max-Age=360', 'Path=/', 'foo="bar baz blub"'])
    assert parse_cookie('fo234{=bar blub=Blah') == {'blub': 'Blah'}


def test_cookie_quoting():
    """Cookie value quoting."""
    val = dump_cookie("foo", "?foo")
    assert val == 'foo="?foo"; Path=/'
    assert parse_cookie(val) == {'foo': '?foo'}


def test_import_string():
    """String based importing"""
    import cgi
    from werkzeug.debug import DebuggedApplication
    assert import_string('cgi.escape') is cgi.escape
    assert import_string(u'cgi.escape') is cgi.escape
    assert import_string('cgi:escape') is cgi.escape
    assert import_string('XXXXXXXXXXXX', True) is None
    assert import_string('cgi.XXXXXXXXXXXX', True) is None
    assert import_string(u'cgi.escape') is cgi.escape
    assert import_string(u'werkzeug.debug.DebuggedApplication') is DebuggedApplication
    assert_raises(ImportError, import_string, 'XXXXXXXXXXXXXXXX')
    assert_raises(AttributeError, import_string, 'cgi.XXXXXXXXXX')


def test_find_modules():
    """Module and package lookup"""
    assert list(find_modules('werkzeug.debug')) == \
        ['werkzeug.debug.console', 'werkzeug.debug.render',
         'werkzeug.debug.repr', 'werkzeug.debug.tbtools',
         'werkzeug.debug.utils']


def test_html_builder():
    """HTML builder"""
    assert html.p('Hello World') == '<p>Hello World</p>'
    assert html.a('Test', href='#') == '<a href="#">Test</a>'
    assert html.br() == '<br>'
    assert xhtml.br() == '<br />'
    assert html.img(src='foo') == '<img src="foo">'
    assert xhtml.img(src='foo') == '<img src="foo" />'
    assert html.html(
        html.head(
            html.title('foo'),
            html.script(type='text/javascript')
        )
    ) == '<html><head><title>foo</title><script type="text/javascript">' \
         '</script></head></html>'
    assert html('<foo>') == '&lt;foo&gt;'


def test_validate_arguments():
    """Function argument validator"""
    take_none = lambda: None
    take_two = lambda a, b: None
    take_two_one_default = lambda a, b=0: None

    assert validate_arguments(take_two, (1, 2,), {}) == ((1, 2), {})
    assert validate_arguments(take_two, (1,), {'b': 2}) == ((1, 2), {})
    assert validate_arguments(take_two_one_default, (1,), {}) == ((1, 0), {})
    assert validate_arguments(take_two_one_default, (1, 2), {}) == ((1, 2), {})

    assert_raises(ArgumentValidationError, validate_arguments, take_two, (), {})

    assert validate_arguments(take_none, (1, 2,), {'c': 3}) == ((), {})
    assert_raises(ArgumentValidationError,
           validate_arguments, take_none, (1,), {}, drop_extra=False)
    assert_raises(ArgumentValidationError,
           validate_arguments, take_none, (), {'a': 1}, drop_extra=False)


def test_header_set_duplication_bug():
    """Header duplication bug on set"""
    from werkzeug.datastructures import Headers
    headers = Headers([
        ('Content-Type', 'text/html'),
        ('Foo', 'bar'),
        ('Blub', 'blah')
    ])
    headers['blub'] = 'hehe'
    headers['blafasel'] = 'humm'
    assert headers == Headers([
        ('Content-Type', 'text/html'),
        ('Foo', 'bar'),
        ('blub', 'hehe'),
        ('blafasel', 'humm')
    ])


def test_append_slash_redirect():
    """Append slash redirect"""
    def app(env, sr):
        return append_slash_redirect(env)(env, sr)
    client = Client(app, BaseResponse)
    response = client.get('foo', base_url='http://example.org/app')
    assert response.status_code == 301
    assert response.headers['Location'] == 'http://example.org/app/foo/'


def test_cached_property_doc():
    """Documentation of cached_property is kept"""
    @cached_property
    def foo():
        """testing"""
        return 42
    assert foo.__doc__ == 'testing'
    assert foo.__name__ == 'foo'
    assert foo.__module__ == __name__
