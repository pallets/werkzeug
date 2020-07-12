import datetime
import io
import os
import pathlib

import pytest

from werkzeug.test import Client
from werkzeug.utils import send_file
from werkzeug.wrappers.response import Response
from werkzeug.wsgi import responder

res_path = os.path.join(os.path.dirname(__file__), "res")
html_path = os.path.join(res_path, "index.html")
txt_path = os.path.join(res_path, "test.txt")


@pytest.mark.parametrize("path", [html_path, pathlib.Path(html_path)])
def test_path(path):
    rv = send_file(path)
    assert rv.mimetype == "text/html"
    assert rv.direct_passthrough
    rv.direct_passthrough = False

    with open(html_path, "rb") as f:
        assert rv.data == f.read()

    rv.close()


def test_x_sendfile():
    rv = send_file(html_path, use_x_sendfile=True)
    assert rv.headers["x-sendfile"] == html_path
    assert rv.data == b""
    rv.close()


def test_last_modified():
    last_modified = datetime.datetime(1999, 1, 1)

    def foo(environ, start_response):
        return send_file(
            io.BytesIO(b"party like it's"),
            environ=environ,
            last_modified=last_modified,
            mimetype="text/plain",
        )

    client = Client(responder(foo), Response)
    rv = client.get("/")
    assert rv.last_modified == last_modified


@pytest.mark.parametrize(
    "file_factory", [lambda: open(txt_path, "rb"), lambda: io.BytesIO(b"test")],
)
def test_object(file_factory):
    rv = send_file(file_factory(), mimetype="text/plain", use_x_sendfile=True)
    rv.direct_passthrough = False
    assert rv.data
    assert rv.mimetype == "text/plain"
    assert "x-sendfile" not in rv.headers
    rv.close()


def test_object_without_mimetype():
    with pytest.raises(ValueError, match="detect the MIME type"):
        send_file(io.BytesIO(b"test"))


def test_object_mimetype_from_attachment():
    rv = send_file(io.BytesIO(b"test"), attachment_filename="test.txt")
    assert rv.mimetype == "text/plain"
    rv.close()


@pytest.mark.parametrize(
    "file_factory", [lambda: open(txt_path), lambda: io.StringIO("test")],
)
def test_text_mode_fails(file_factory):
    with file_factory() as f, pytest.raises(ValueError, match="binary mode"):
        send_file(f, os.path.realpath(__file__), mimetype="text/plain")


@pytest.mark.parametrize(
    ("filename", "ascii", "utf8"),
    (
        ("index.html", "index.html", None),
        (
            "Ñandú／pingüino.txt",
            '"Nandu/pinguino.txt"',
            "%C3%91and%C3%BA%EF%BC%8Fping%C3%BCino.txt",
        ),
        # latin-1 isn't ascii, should be quoted
        ("Vögel.txt", "Vogel.txt", "V%C3%B6gel.txt"),
        # ":/" are not safe in filename* value
        ("те:/ст", '":/"', "%D1%82%D0%B5%3A%2F%D1%81%D1%82"),
    ),
)
def test_non_ascii_filename(filename, ascii, utf8):
    rv = send_file(html_path, as_attachment=True, attachment_filename=filename)
    rv.close()
    content_disposition = rv.headers["Content-Disposition"]
    assert f"filename={ascii}" in content_disposition

    if utf8:
        assert f"filename*=UTF-8''{utf8}" in content_disposition
    else:
        assert "filename*=UTF-8''" not in content_disposition
