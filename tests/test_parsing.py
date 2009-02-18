# -*- coding: utf-8 -*-
from os.path import join, dirname, abspath
from werkzeug import Client, Request, Response


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
