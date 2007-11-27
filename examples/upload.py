#!/usr/bin/env python
"""
    Simple Upload Application
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    All uploaded files are directly send back to the client.

    :copyright: 2007 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import BaseRequest, BaseResponse, run_simple


def view_file(req):
    if not 'uploaded_file' in req.files:
        return BaseResponse('no file uploaded')
    f = req.files['uploaded_file']
    def stream():
        while 1:
            data = f.read(65536)
            if not data:
                break
            yield data
    return BaseResponse(stream(), mimetype=f.content_type)


def upload_file(req):
    return BaseResponse('''
    <h1>Upload File</h1>
    <form action="" method="post" enctype="multipart/form-data">
        <input type="file" name="uploaded_file">
        <input type="submit" value="Upload">
    </form>
    ''', mimetype='text/html')


def application(environ, start_response):
    req = BaseRequest(environ)
    if req.method == 'POST':
        resp = view_file(req)
    else:
        resp = upload_file(req)
    return resp(environ, start_response)


if __name__ == '__main__':
    run_simple('localhost', 5000, application)
