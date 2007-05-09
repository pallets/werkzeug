#!/usr/bin/env python
from werkzeug.wrappers import BaseRequest, BaseResponse


class Request(BaseRequest):
    charset = 'utf-8'

class Response(BaseResponse):
    charset = 'utf-8'


def view_file(req):
    if not 'uploaded_file' in req.files:
        return Response('no file uploaded')
    f = req.files['uploaded_file']
    return Response(f.read(), mimetype=f.content_type)


def upload_file(req):
    return Response('''
    <h1>Upload File</h1>
    <form action="" method="post" enctype="multipart/form-data">
        <input type="file" name="uploaded_file">
        <input type="submit" value="Upload">
    </form>
    ''', mimetype='text/html')


def application(environ, start_response):
    req = Request(environ)
    if req.method == 'POST':
        resp = view_file(req)
    else:
        resp = upload_file(req)
    return resp(environ, start_response)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    srv = make_server('localhost', 5000, application)
    srv.serve_forever()
