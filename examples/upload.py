"""All uploaded files are directly send back to the client."""
from werkzeug.serving import run_simple
from werkzeug.utils import send_file
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file


def view_file(req):
    if (f := req.files.get("uploaded_file")) is None:
        return Response("no file uploaded")

    return send_file(f, req.environ, mimetype=f.mimetype)


def upload_file(req):
    return Response(
        """<h1>Upload File</h1>
        <form action="" method="post" enctype="multipart/form-data">
            <input type="file" name="uploaded_file">
            <input type="submit" value="Upload">
        </form>""",
        mimetype="text/html",
    )


def application(environ, start_response):
    req = Request(environ)
    if req.method == "POST":
        resp = view_file(req)
    else:
        resp = upload_file(req)
    return resp(environ, start_response)


if __name__ == "__main__":
    run_simple("localhost", 5000, application, use_debugger=True)
