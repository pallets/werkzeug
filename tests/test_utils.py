# -*- coding: utf-8 -*-
"""
    werkzeug.utils test
    ~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import sys
from datetime import datetime
from os import path
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


def test_quoting():
    """URL quoting"""
    assert url_quote(u'\xf6\xe4\xfc') == '%C3%B6%C3%A4%C3%BC'
    assert url_unquote(url_quote(u'#%="\xf6')) == u'#%="\xf6'
    assert url_quote_plus('foo bar') == 'foo+bar'
    assert url_unquote_plus('foo+bar') == 'foo bar'
    assert url_encode({'a': None, 'b': 'foo bar'}) == 'b=foo+bar'
    assert url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)') == \
           'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'


def test_url_decoding():
    """Test the URL decoding"""
    x = url_decode('foo=42&bar=23&uni=H%C3%A4nsel')
    assert x['foo'] == '42'
    assert x['bar'] == '23'
    assert x['uni'] == u'Hänsel'

    x = url_decode('foo=42;bar=23;uni=H%C3%A4nsel', separator=';')
    assert x['foo'] == '42'
    assert x['bar'] == '23'
    assert x['uni'] == u'Hänsel'

    x = url_decode('%C3%9Ch=H%C3%A4nsel', decode_keys=True)
    assert x[u'Üh'] == u'Hänsel'


def test_url_encoding():
    """Test the URL decoding"""
    assert url_encode({'foo': 'bar 45'}) == 'foo=bar+45'
    d = {'foo': 1, 'bar': 23, 'blah': u'Hänsel'}
    assert url_encode(d, sort=True) == 'bar=23&blah=H%C3%A4nsel&foo=1'
    assert url_encode(d, sort=True, separator=';') == 'bar=23;blah=H%C3%A4nsel;foo=1'


def test_sorted_url_encode():
    """Optional sorted URL encoding"""
    assert url_encode({"a": 42, "b": 23, 1: 1, 2: 2}, sort=True) == '1=1&2=2&a=42&b=23'
    assert url_encode({'A': 1, 'a': 2, 'B': 3, 'b': 4}, sort=True,
                      key=lambda x: x[0].lower()) == 'A=1&a=2&B=3&b=4'


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


def test_shared_data_middleware():
    """Shared data middleware"""
    def null_application(environ, start_response):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        yield 'NOT FOUND'
    app = SharedDataMiddleware(null_application, {
        '/':        path.join(path.dirname(__file__), 'res'),
        '/sources': path.join(path.dirname(__file__), 'res'),
        '/pkg':     ('werkzeug.debug', 'shared')
    })

    for p in '/test.txt', '/sources/test.txt':
        app_iter, status, headers = run_wsgi_app(app, create_environ(p))
        assert status == '200 OK'
        assert ''.join(app_iter).strip() == 'FOUND'

    app_iter, status, headers = run_wsgi_app(app, create_environ('/pkg/body.tmpl'))
    contents = ''.join(app_iter)
    assert 'Werkzeug Debugger' in contents

    app_iter, status, headers = run_wsgi_app(app, create_environ('/missing'))
    assert status == '404 NOT FOUND'
    assert ''.join(app_iter).strip() == 'NOT FOUND'


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


def test_get_host():
    """Host lookup"""
    env = {'HTTP_X_FORWARDED_HOST': 'example.org',
           'SERVER_NAME': 'bullshit', 'HOST_NAME': 'ignore me dammit'}
    assert get_host(env) == 'example.org'
    assert get_host(create_environ('/', 'http://example.org')) \
        == 'example.org'


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


def test_responder():
    """Responder decorator"""
    def foo(environ, start_response):
        return BaseResponse('Test')
    client = Client(responder(foo), BaseResponse)
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == 'Test'


def test_import_string():
    """String based importing"""
    import cgi
    assert import_string('cgi.escape') is cgi.escape
    assert import_string('cgi:escape') is cgi.escape
    assert import_string('XXXXXXXXXXXX', True) is None
    assert import_string('cgi.XXXXXXXXXXXX', True) is None
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


def test_shareddatamiddleware_get_file_loader():
    """Shared middleware file loader lookup"""
    app = SharedDataMiddleware(None, {})
    assert callable(app.get_file_loader('foo'))


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


def test_parse_form_data_put_without_content():
    """A PUT without a Content-Type header returns empty data

    Both rfc1945 and rfc2616 (1.0 and 1.1) say "Any HTTP/[1.0/1.1] message
    containing an entity-body SHOULD include a Content-Type header field
    defining the media type of that body."  In the case where either
    headers are omitted, parse_form_data should still work.
    """
    env = create_environ('/foo', 'http://example.org/', method='PUT')
    del env['CONTENT_TYPE']
    del env['CONTENT_LENGTH']

    stream, form, files = parse_form_data(env)
    assert stream.read() == ""
    assert len(form) == 0
    assert len(files) == 0


def test_parse_form_data_get_without_content():
    """GET requests without data, content type and length returns no data"""
    env = create_environ('/foo', 'http://example.org/', method='GET')
    del env['CONTENT_TYPE']
    del env['CONTENT_LENGTH']

    stream, form, files = parse_form_data(env)
    assert stream.read() == ""
    assert len(form) == 0
    assert len(files) == 0


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


def test_pop_path_info():
    """Test path info popping in the utils"""
    original_env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/a/b///c'}

    # regular path info popping
    def assert_tuple(script_name, path_info):
        assert env.get('SCRIPT_NAME') == script_name
        assert env.get('PATH_INFO') == path_info
    env = original_env.copy()
    pop = lambda: pop_path_info(env)

    assert_tuple('/foo', '/a/b///c')
    assert pop() == 'a'
    assert_tuple('/foo/a', '/b///c')
    assert pop() == 'b'
    assert_tuple('/foo/a/b', '///c')
    assert pop() == 'c'
    assert_tuple('/foo/a/b///c', '')
    assert pop() is None


def test_peek_path_info():
    """Test path info peeking in wrappers and utils"""
    env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/aaa/b///c'}

    assert peek_path_info(env) == 'aaa'
    assert peek_path_info(env) == 'aaa'


def test_limited_stream():
    """Test the LimitedStream"""
    io = StringIO('123456')
    stream = LimitedStream(io, 3, False)
    assert stream.read() == '123'
    assert_raises(BadRequest, stream.read)

    io = StringIO('123456')
    stream = LimitedStream(io, 3, False)
    assert stream.read(1) == '1'
    assert stream.read(1) == '2'
    assert stream.read(1) == '3'
    assert_raises(BadRequest, stream.read)

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readline() == '123456\n'
    assert stream.readline() == 'ab'

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines() == ['123456\n', 'ab']

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines(2) == ['12']
    assert stream.readlines(2) == ['34']
    assert stream.readlines() == ['56\n', 'ab']

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readline(100) == '123456\n'

    io = StringIO('123456\nabcdefg')
    stream = LimitedStream(io, 9)
    assert stream.readlines(100) == ['123456\n', 'ab']

    io = StringIO('123456')
    stream = LimitedStream(io, 3)
    assert stream.read(1) == '1'
    assert stream.read(1) == '2'
    assert stream.read() == '3'
    assert stream.read() == ''


def test_file_storage_truthiness():
    """Test FileStorage truthiness"""
    fs = FileStorage()
    assert not fs, 'should be False'

    fs = FileStorage(StringIO('Hello World'), filename='foo.txt')
    assert fs, 'should be True because of a provided filename'
