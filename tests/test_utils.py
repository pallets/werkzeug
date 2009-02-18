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
from werkzeug.test import Client


def test_import_patch():
    """Import patch"""
    import werkzeug
    from werkzeug import __all__ as public_methods
    for name in public_methods:
        getattr(werkzeug, name)


def test_multidict():
    """Multidict behavior"""
    md = MultiDict()
    assert isinstance(md, dict)

    mapping = [('a', 1), ('b', 2), ('a', 2), ('d', 3),
               ('a', 1), ('a', 3), ('d', 4), ('c', 3)]
    md = MultiDict(mapping)

    # simple getitem gives the first value
    assert md['a'] == 1
    assert md['c'] == 3
    assert_raises(KeyError, lambda: md['e'])
    assert md.get('a') == 1

    # list getitem
    assert md.getlist('a') == [1, 2, 1, 3]
    assert md.getlist('d') == [3, 4]
    # do not raise if key not found
    assert md.getlist('x') == []

    # simple setitem overwrites all values
    md['a'] = 42
    assert md.getlist('a') == [42]

    # list setitem
    md.setlist('a', [1, 2, 3])
    assert md['a'] == 1
    assert md.getlist('a') == [1, 2, 3]

    # verify that it does not change original lists
    l1 = [1, 2, 3]
    md.setlist('a', l1)
    del l1[:]
    assert md['a'] == 1

    # setdefault, setlistdefault
    assert md.setdefault('u', 23) == 23
    assert md.getlist('u') == [23]
    del md['u']

    assert md.setlistdefault('u', [-1, -2]) == [-1, -2]
    assert md.getlist('u') == [-1, -2]
    assert md['u'] == -1

    # delitem
    del md['u']
    assert_raises(KeyError, lambda: md['u'])
    del md['d']
    assert md.getlist('d') == []

    # keys, values, items, lists
    assert list(sorted(md.keys())) == ['a', 'b', 'c']
    assert list(sorted(md.iterkeys())) == ['a', 'b', 'c']

    assert list(sorted(md.values())) == [1, 2, 3]
    assert list(sorted(md.itervalues())) == [1, 2, 3]

    assert list(sorted(md.items())) == [('a', 1), ('b', 2), ('c', 3)]
    assert list(sorted(md.iteritems())) == [('a', 1), ('b', 2), ('c', 3)]

    assert list(sorted(md.lists())) == [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]
    assert list(sorted(md.iterlists())) == [('a', [1, 2, 3]), ('b', [2]), ('c', [3])]

    # copy method
    copy = md.copy()
    assert copy['a'] == 1
    assert copy.getlist('a') == [1, 2, 3]

    # update with a multidict
    od = MultiDict([('a', 4), ('a', 5), ('y', 0)])
    md.update(od)
    assert md.getlist('a') == [1, 2, 3, 4, 5]
    assert md.getlist('y') == [0]

    # update with a regular dict
    md = copy
    od = {'a': 4, 'y': 0}
    md.update(od)
    assert md.getlist('a') == [1, 2, 3, 4]
    assert md.getlist('y') == [0]

    # pop, poplist, popitem, popitemlist
    assert md.pop('y') == 0
    assert 'y' not in md
    assert md.poplist('a') == [1, 2, 3, 4]
    assert 'a' not in md
    assert md.poplist('missing') == []

    # remaining: b=2, c=3
    popped = md.popitem()
    assert popped in [('b', 2), ('c', 3)]
    popped = md.popitemlist()
    assert popped in [('b', [2]), ('c', [3])]

    # type conversion
    md = MultiDict({'a': '4', 'b': ['2', '3']})
    assert md.get('a', type=int) == 4
    assert md.getlist('b', type=int) == [2, 3]


def test_combined_multidict():
    """Combined multidict behavior"""
    d1 = MultiDict([('foo', '1')])
    d2 = MultiDict([('bar', '2'), ('bar', '3')])
    d = CombinedMultiDict([d1, d2])

    # lookup
    assert d['foo'] == '1'
    assert d['bar'] == '2'
    assert d.getlist('bar') == ['2', '3']

    # type lookup
    assert d.get('foo', type=int) == 1
    assert d.getlist('bar', type=int) == [2, 3]

    # get key errors for missing stuff
    assert_raises(KeyError, lambda: d["missing"])

    # make sure that they are immutable
    def test_assign():
        d['foo'] = 'blub'
    assert_raises(TypeError, test_assign)


def test_headers():
    # simple header tests
    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('X-Foo', 'bar')
    assert 'x-Foo' in headers
    assert 'Content-type' in headers

    headers['Content-Type'] = 'foo/bar'
    assert headers['Content-Type'] == 'foo/bar'
    assert len(headers.getlist('Content-Type')) == 1

    # list conversion
    assert headers.to_list() == [
        ('Content-Type', 'foo/bar'),
        ('X-Foo', 'bar')
    ]
    assert str(headers) == (
        "Content-Type: foo/bar\r\n"
        "X-Foo: bar\r\n"
        "\r\n")
    assert str(Headers()) == "\r\n"

    # extended add
    headers.add('Content-Disposition', 'attachment', filename='foo')
    assert headers['Content-Disposition'] == 'attachment; filename="foo"'

    headers.add('x', 'y', z='"')
    assert headers['x'] == r'y; z="\""'

    # defaults
    headers = Headers({
        'Content-Type': 'text/plain',
        'X-Foo':        'bar',
        'X-Bar':        ['1', '2']
    })
    assert headers.getlist('x-bar') == ['1', '2']
    assert headers.get('x-Bar') == '1'
    assert headers.get('Content-Type') == 'text/plain'

    assert headers.setdefault('X-Foo', 'nope') == 'bar'
    assert headers.setdefault('X-Bar', 'nope') == '1'
    assert headers.setdefault('X-Baz', 'quux') == 'quux'
    assert headers.setdefault('X-Baz', 'nope') == 'quux'
    headers.pop('X-Baz')

    # type conversion
    assert headers.get('x-bar', type=int) == 1
    assert headers.getlist('x-bar', type=int) == [1, 2]

    # list like operations
    assert headers[0] == ('Content-Type', 'text/plain')
    assert headers[:1] == Headers([('Content-Type', 'text/plain')])
    del headers[:2]
    del headers[-1]
    assert headers == Headers([('X-Bar', '2')])

    # copying
    a = Headers([('foo', 'bar')])
    b = a.copy()
    a.add('foo', 'baz')
    assert a.getlist('foo') == ['bar', 'baz']
    assert b.getlist('foo') == ['bar']

    headers = Headers([('a', 1)])
    assert headers.pop('a') == 1
    assert headers.pop('b', 2) == 2
    assert_raises(KeyError, headers.pop, 'c')


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


def test_create_environ():
    """Environment creation helper"""
    env = create_environ('/foo?bar=baz', 'http://example.org/')
    expected = {
        'wsgi.multiprocess':    False,
        'wsgi.version':         (1, 0),
        'wsgi.run_once':        False,
        'wsgi.errors':          sys.stderr,
        'wsgi.multithread':     False,
        'wsgi.url_scheme':      'http',
        'SCRIPT_NAME':          '/',
        'CONTENT_TYPE':         '',
        'CONTENT_LENGTH':       '0',
        'SERVER_NAME':          'example.org',
        'REQUEST_METHOD':       'GET',
        'HTTP_HOST':            'example.org',
        'PATH_INFO':            '/foo',
        'SERVER_PORT':          '80',
        'SERVER_PROTOCOL':      'HTTP/1.0',
        'QUERY_STRING':         'bar=baz'
    }
    for key, value in expected.iteritems():
        assert env[key] == value
    assert env['wsgi.input'].read(0) == ''


def test_shared_data_middleware():
    """Shared data middleware"""
    def null_application(environ, start_response):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        yield 'NOT FOUND'
    app = SharedDataMiddleware(null_application, {
        '/':        path.join(path.dirname(__file__), 'res'),
        '/sources': path.join(path.dirname(__file__), 'res')
    })

    for p in '/test.txt', '/sources/test.txt':
        app_iter, status, headers = run_wsgi_app(app, create_environ(p))
        assert status == '200 OK'
        assert ''.join(app_iter).strip() == 'FOUND'

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
           set(['HttpOnly', 'Max-Age=360', 'Path=/', 'foo=bar baz blub'])
    assert parse_cookie('fo234{=bar blub=Blah') == {'blub': 'Blah'}


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
    """Test path info popping in wrappers and utils"""
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

    # request based path info popping, with multi slash
    # removal if they are in prominent places (descriptor magic)
    def assert_tuple(script_name, path_info):
        assert req.script_root == script_name
        assert req.path == path_info
    req = Request(original_env.copy())
    pop = req.pop_path_info

    assert_tuple(u'/foo', u'/a/b///c')
    assert pop() == 'a'
    assert_tuple(u'/foo/a', u'/b///c')
    assert pop() == 'b'
    assert_tuple(u'/foo/a/b', u'/c')
    assert pop() == 'c'
    assert_tuple(u'/foo/a/b///c', u'/')
    assert pop() is None


def test_peek_path_info():
    """Test path info peeking in wrappers and utils"""
    env = {'SCRIPT_NAME': '/foo', 'PATH_INFO': '/aaa/b///c'}
    req = Request(env)

    assert peek_path_info(env) == 'aaa'
    assert peek_path_info(env) == 'aaa'

    assert req.peek_path_info() == 'aaa'
    assert req.peek_path_info() == 'aaa'


def test_limited_stream():
    """Test the LimitedStream"""
    io = StringIO('123456')
    stream = LimitedStream(io, 3)
    assert stream.read() == '123'
    assert_raises(BadRequest, stream.read)

    io = StringIO('123456')
    stream = LimitedStream(io, 3)
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
