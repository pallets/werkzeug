#!/usr/bin/env python
"""
    Simple Upload Application
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    All uploaded files are directly send back to the client.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from werkzeug.serving import run_simple
from werkzeug.wrappers import BaseRequest
from werkzeug.wrappers import BaseResponse
from werkzeug.wsgi import wrap_file


def view_file(req):
    if "uploaded_file" not in req.files:
        return BaseResponse("no file uploaded")
    f = req.files["uploaded_file"]
    return BaseResponse(
        wrap_file(req.environ, f), mimetype=f.content_type, direct_passthrough=True
    )


def upload_file(req):
    return BaseResponse(
        """<h1>Upload File</h1>
        <form action="" method="post" enctype="multipart/form-data">
            <input type="file" name="uploaded_file">
            <input type="submit" value="Upload">
        </form>""",
        mimetype="text/html",
    )


def application(environ, start_response):
    req = BaseRequest(environ)
    if req.method == "POST":
        resp = view_file(req)
    else:
        resp = upload_file(req)
    return resp(environ, start_response)


if __name__ == "__main__":
    run_simple("localhost", 5000, application, use_debugger=True)
