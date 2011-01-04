#!/usr/bin/env python
"""
    Simple Upload Application
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    All uploaded files are directly send back to the client.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.serving import run_simple
from werkzeug.wrappers import BaseRequest, BaseResponse
from werkzeug.wsgi import wrap_file


def view_file(req):
    if not 'uploaded_file' in req.files:
        return BaseResponse('no file uploaded')
    f = req.files['uploaded_file']
    return BaseResponse(wrap_file(req.environ, f), mimetype=f.content_type,
                        direct_passthrough=True)


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
    run_simple('localhost', 5000, application, use_debugger=True)
