# -*- coding: utf-8 -*-
"""
    werkzeug.formparser test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Tests the form parsing capabilties.  Some of them are also tested from
    the wrappers.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from nose.tools import assert_raises
from os.path import join, dirname, abspath
from cStringIO import StringIO

from werkzeug import Client, Request, Response, parse_form_data, \
     create_environ, FileStorage, formparser, create_environ
from werkzeug.exceptions import RequestEntityTooLarge


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


@Request.application
def form_data_consumer(request):
    result_object = request.args['object']
    if result_object == 'text':
        return Response(repr(request.form['text']))
    f = request.files[result_object]
    return Response('\n'.join((
        repr(f.filename),
        repr(f.name),
        repr(f.content_type),
        f.stream.read()
    )))


def get_contents(filename):
    f = file(filename, 'rb')
    try:
        return f.read()
    finally:
        f.close()


def test_multipart():
    """Tests multipart parsing against data collected from webbrowsers"""
    resources = join(dirname(__file__), 'multipart')
    client = Client(form_data_consumer, Response)

    repository = [
        ('firefox3-2png1txt', '---------------------------186454651713519341951581030105', [
            (u'anchor.png', 'file1', 'image/png', 'file1.png'),
            (u'application_edit.png', 'file2', 'image/png', 'file2.png')
        ], u'example text'),
        ('firefox3-2pnglongtext', '---------------------------14904044739787191031754711748', [
            (u'accept.png', 'file1', 'image/png', 'file1.png'),
            (u'add.png', 'file2', 'image/png', 'file2.png')
        ], u'--long text\r\n--with boundary\r\n--lookalikes--'),
        ('opera8-2png1txt', '----------zEO9jQKmLc2Cq88c23Dx19', [
            (u'arrow_branch.png', 'file1', 'image/png', 'file1.png'),
            (u'award_star_bronze_1.png', 'file2', 'image/png', 'file2.png')
        ], u'blafasel öäü'),
        ('webkit3-2png1txt', '----WebKitFormBoundaryjdSFhcARk8fyGNy6', [
            (u'gtk-apply.png', 'file1', 'image/png', 'file1.png'),
            (u'gtk-no.png', 'file2', 'image/png', 'file2.png')
        ], u'this is another text with ümläüts'),
        ('ie6-2png1txt', '---------------------------7d91b03a20128', [
            (u'file1.png', 'file1', 'image/x-png', 'file1.png'),
            (u'file2.png', 'file2', 'image/x-png', 'file2.png')
        ], u'ie6 sucks :-/')
    ]

    for name, boundary, files, text in repository:
        folder = join(resources, name)
        data = get_contents(join(folder, 'request.txt'))
        for filename, field, content_type, fsname in files:
            response = client.post('/?object=' + field, data=data, content_type=
                                   'multipart/form-data; boundary="%s"' % boundary,
                                   content_length=len(data))
            lines = response.data.split('\n', 3)
            assert lines[0] == repr(filename)
            assert lines[1] == repr(field)
            assert lines[2] == repr(content_type)
            assert lines[3] == get_contents(join(folder, fsname))
        response = client.post('/?object=text', data=data, content_type=
                               'multipart/form-data; boundary="%s"' % boundary,
                               content_length=len(data))
        assert response.data == repr(text)

def test_ie7_unc_path():
    client = Client(form_data_consumer, Response)
    data_file = join(dirname(__file__), 'multipart', 'ie7_full_path_request.txt')
    data = get_contents(data_file)
    boundary = '---------------------------7da36d1b4a0164'
    response = client.post('/?object=cb_file_upload_multiple', data=data, content_type=
                               'multipart/form-data; boundary="%s"' % boundary, content_length=len(data))
    lines = response.data.split('\n', 3)
    assert lines[0] == repr(u'Sellersburg Town Council Meeting 02-22-2010doc.doc'), lines[0]
    
def test_end_of_file_multipart():
    """Test for multipart files ending unexpectedly"""
    # This test looks innocent but it was actually timeing out in
    # the Werkzeug 0.5 release version (#394)
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n'
        'Content-Type: text/plain\r\n\r\n'
        'file contents and no end'
    )
    data = Request.from_values(input_stream=StringIO(data),
                               content_length=len(data),
                               content_type='multipart/form-data; boundary=foo',
                               method='POST')
    assert not data.files
    assert not data.form


def test_broken_multipart():
    """Broken multipart does not break the applicaiton"""
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n'
        'Content-Transfer-Encoding: base64\r\n'
        'Content-Type: text/plain\r\n\r\n'
        'broken base 64'
        '--foo--'
    )
    _, form, files = parse_form_data(create_environ(data=data, method='POST',
                                     content_type='multipart/form-data; boundary=foo'))
    assert not files
    assert not form

    assert_raises(ValueError, parse_form_data, create_environ(data=data, method='POST',
                  content_type='multipart/form-data; boundary=foo'),
                  silent=False)


def test_multipart_file_no_content_type():
    """Chrome does not always provide a content type."""
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n\r\n'
        'file contents\r\n--foo--'
    )
    data = Request.from_values(input_stream=StringIO(data),
                               content_length=len(data),
                               content_type='multipart/form-data; boundary=foo',
                               method='POST')
    assert data.files['test'].filename == 'test.txt'
    assert data.files['test'].read() == 'file contents'


def test_extra_newline_multipart():
    """Test for multipart uploads with extra newlines"""
    # this test looks innocent but it was actually timeing out in
    # the Werkzeug 0.5 release version (#394)
    data = (
        '\r\n\r\n--foo\r\n'
        'Content-Disposition: form-data; name="foo"\r\n\r\n'
        'a string\r\n'
        '--foo--'
    )
    data = Request.from_values(input_stream=StringIO(data),
                               content_length=len(data),
                               content_type='multipart/form-data; boundary=foo',
                               method='POST')
    assert not data.files
    assert data.form['foo'] == 'a string'


def test_multipart_headers():
    """Test access to multipart headers"""
    data = ('--foo\r\n'
            'Content-Disposition: form-data; name="foo"; filename="foo.txt"\r\n'
            'X-Custom-Header: blah\r\n'
            'Content-Type: text/plain; charset=utf-8\r\n\r\n'
            'file contents, just the contents\r\n'
            '--foo--')
    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='multipart/form-data; boundary=foo',
                              method='POST')
    foo = req.files['foo']
    assert foo.content_type == 'text/plain'
    assert foo.headers['content-type'] == 'text/plain; charset=utf-8'
    assert foo.headers['x-custom-header'] == 'blah'


def test_nonstandard_line_endings():
    """Test nonstandard line endings of multipart form data"""
    for nl in '\n', '\r', '\r\n':
        data = nl.join((
            '--foo',
            'Content-Disposition: form-data; name=foo',
            '',
            'this is just bar',
            '--foo',
            'Content-Disposition: form-data; name=bar',
            '',
            'blafasel',
            '--foo--'
        ))
        req = Request.from_values(input_stream=StringIO(data),
                                  content_length=len(data),
                                  content_type='multipart/form-data; '
                                  'boundary=foo', method='POST')
        print req.form
        assert req.form['foo'] == 'this is just bar'
        assert req.form['bar'] == 'blafasel'


def test_limiting():
    """Test the limiting features"""
    data = 'foo=Hello+World&bar=baz'
    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='application/x-www-form-urlencoded',
                              method='POST')
    req.max_content_length = 4

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='application/x-www-form-urlencoded',
                              method='POST')
    req.max_content_length = 400
    assert req.form['foo'] == 'Hello World'

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='application/x-www-form-urlencoded',
                              method='POST')
    req.max_form_memory_size = 7
    assert_raises(RequestEntityTooLarge, lambda: req.form['foo'])

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='application/x-www-form-urlencoded',
                              method='POST')
    req.max_form_memory_size = 400
    assert req.form['foo'] == 'Hello World'

    data = ('--foo\r\nContent-Disposition: form-field; name=foo\r\n\r\n'
            'Hello World\r\n'
            '--foo\r\nContent-Disposition: form-field; name=bar\r\n\r\n'
            'bar=baz\r\n--foo--')
    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='multipart/form-data; boundary=foo',
                              method='POST')
    req.max_content_length = 4
    assert_raises(RequestEntityTooLarge, lambda: req.form['foo'])

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='multipart/form-data; boundary=foo',
                              method='POST')
    req.max_content_length = 400
    assert req.form['foo'] == 'Hello World'

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='multipart/form-data; boundary=foo',
                              method='POST')
    req.max_form_memory_size = 7
    assert_raises(RequestEntityTooLarge, lambda: req.form['foo'])

    req = Request.from_values(input_stream=StringIO(data),
                              content_length=len(data),
                              content_type='multipart/form-data; boundary=foo',
                              method='POST')
    req.max_form_memory_size = 400
    assert req.form['foo'] == 'Hello World'


def test_large_file():
    """Test a largish file."""
    data = 'x' * (1024 * 600)
    req = Request.from_values(data={'foo': (StringIO(data), 'test.txt')},
                              method='POST')
    # make sure we have a real file here, because we expect to be
    # on the disk.  > 1024 * 500
    assert isinstance(req.files['foo'].stream, file)


def test_lowlevel():
    """Lowlevel formparser tests"""
    formparser._line_parse('foo') == ('foo', False)
    formparser._line_parse('foo\r\n') == ('foo', True)
    formparser._line_parse('foo\r') == ('foo', True)
    formparser._line_parse('foo\n') == ('foo', True)

    lineiter = iter('\n\n\nfoo\nbar\nbaz'.splitlines(True))
    line = formparser._find_terminator(lineiter)
    assert line == 'foo'
    assert list(lineiter) == ['bar\n', 'baz']
    assert formparser._find_terminator([]) == ''
    assert formparser._find_terminator(['']) == ''

    assert_raises(ValueError, formparser.parse_multipart, None, '', 20)
    assert_raises(ValueError, formparser.parse_multipart, None, 'broken  ', 20)

    data = '--foo\r\n\r\nHello World\r\n--foo--'
    assert_raises(ValueError, formparser.parse_multipart, StringIO(data), 'foo', len(data))

    data = '--foo\r\nContent-Disposition: form-field; name=foo\r\n' \
           'Content-Transfer-Encoding: base64\r\n\r\nHello World\r\n--foo--'
    assert_raises(ValueError, formparser.parse_multipart, StringIO(data), 'foo', len(data))

    data = '--foo\r\nContent-Disposition: form-field; name=foo\r\n\r\nHello World\r\n'
    assert_raises(ValueError, formparser.parse_multipart, StringIO(data), 'foo', len(data))

    x = formparser.parse_multipart_headers(['foo: bar\r\n', ' x test\r\n'])
    assert x['foo'] == 'bar\n x test'
    assert_raises(ValueError, formparser.parse_multipart_headers, ['foo: bar\r\n', ' x test'])
