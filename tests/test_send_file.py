import datetime
import io
import os
import pathlib

import pytest

from werkzeug.test import EnvironBuilder
from werkzeug.utils import send_file

res_path = pathlib.Path(__file__).parent / "res"
html_path = res_path / "index.html"
txt_path = res_path / "test.txt"


@pytest.mark.parametrize("path", [html_path, str(html_path)])
def test_path(path):
    rv = send_file(path)
    assert rv.mimetype == "text/html"
    assert rv.direct_passthrough
    rv.direct_passthrough = False
    assert rv.data == html_path.read_bytes()
    rv.close()


def test_x_sendfile():
    rv = send_file(html_path, use_x_sendfile=True)
    assert rv.headers["x-sendfile"] == str(html_path)
    assert rv.data == b""
    rv.close()


def test_last_modified():
    environ = EnvironBuilder().get_environ()
    last_modified = datetime.datetime(1999, 1, 1)
    rv = send_file(txt_path, environ=environ, last_modified=last_modified)
    assert rv.last_modified == last_modified
    rv.close()


@pytest.mark.parametrize(
    "file_factory", [lambda: txt_path.open("rb"), lambda: io.BytesIO(b"test")],
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
    "file_factory", [lambda: txt_path.open(), lambda: io.StringIO("test")],
)
def test_text_mode_fails(file_factory):
    with file_factory() as f, pytest.raises(ValueError, match="binary mode"):
        send_file(f, os.path.realpath(__file__), mimetype="text/plain")


@pytest.mark.parametrize(
    ("name", "ascii", "utf8"),
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
def test_non_ascii_filename(name, ascii, utf8):
    rv = send_file(html_path, as_attachment=True, attachment_filename=name)
    rv.close()
    content_disposition = rv.headers["Content-Disposition"]
    assert f"filename={ascii}" in content_disposition

    if utf8:
        assert f"filename*=UTF-8''{utf8}" in content_disposition
    else:
        assert "filename*=UTF-8''" not in content_disposition
