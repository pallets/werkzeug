import datetime
import io
import pathlib

import pytest

from werkzeug.http import http_date
from werkzeug.test import EnvironBuilder
from werkzeug.utils import send_file

res_path = pathlib.Path(__file__).parent / "res"
html_path = res_path / "index.html"
txt_path = res_path / "test.txt"

environ = EnvironBuilder().get_environ()


@pytest.mark.parametrize("path", [html_path, str(html_path)])
def test_path(path):
    rv = send_file(path, environ)
    assert rv.mimetype == "text/html"
    assert rv.direct_passthrough
    rv.direct_passthrough = False
    assert rv.data == html_path.read_bytes()
    rv.close()


def test_x_sendfile():
    rv = send_file(html_path, environ, use_x_sendfile=True)
    assert rv.headers["x-sendfile"] == str(html_path)
    assert rv.data == b""
    rv.close()


def test_last_modified():
    last_modified = datetime.datetime(1999, 1, 1)
    rv = send_file(txt_path, environ, last_modified=last_modified)
    assert rv.last_modified == last_modified
    rv.close()


@pytest.mark.parametrize(
    "file_factory", [lambda: txt_path.open("rb"), lambda: io.BytesIO(b"test")],
)
def test_object(file_factory):
    rv = send_file(file_factory(), environ, mimetype="text/plain", use_x_sendfile=True)
    rv.direct_passthrough = False
    assert rv.data
    assert rv.mimetype == "text/plain"
    assert "x-sendfile" not in rv.headers
    rv.close()


def test_object_without_mimetype():
    with pytest.raises(ValueError, match="detect the MIME type"):
        send_file(io.BytesIO(b"test"), environ)


def test_object_mimetype_from_name():
    rv = send_file(io.BytesIO(b"test"), environ, download_name="test.txt")
    assert rv.mimetype == "text/plain"
    rv.close()


@pytest.mark.parametrize(
    "file_factory", [lambda: txt_path.open(), lambda: io.StringIO("test")],
)
def test_text_mode_fails(file_factory):
    with file_factory() as f, pytest.raises(ValueError, match="binary mode"):
        send_file(f, environ, mimetype="text/plain")


@pytest.mark.parametrize(
    ("as_attachment", "value"), [(False, "inline"), (True, "attachment")]
)
def test_disposition_name(as_attachment, value):
    rv = send_file(txt_path, environ, as_attachment=as_attachment)
    assert rv.headers["Content-Disposition"] == f"{value}; filename=test.txt"
    rv.close()


def test_object_attachment_requires_name():
    with pytest.raises(TypeError, match="attachment"):
        send_file(
            io.BytesIO(b"test"), environ, mimetype="text/plain", as_attachment=True,
        )

    rv = send_file(
        io.BytesIO(b"test"), environ, as_attachment=True, download_name="test.txt",
    )
    assert rv.headers["Content-Disposition"] == f"attachment; filename=test.txt"
    rv.close()


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
def test_non_ascii_name(name, ascii, utf8):
    rv = send_file(html_path, environ, as_attachment=True, download_name=name)
    rv.close()
    content_disposition = rv.headers["Content-Disposition"]
    assert f"filename={ascii}" in content_disposition

    if utf8:
        assert f"filename*=UTF-8''{utf8}" in content_disposition
    else:
        assert "filename*=UTF-8''" not in content_disposition


def test_no_cache_conditional_default():
    rv = send_file(
        txt_path,
        EnvironBuilder(
            headers={"If-Modified-Since": http_date(datetime.datetime(2020, 7, 12))}
        ).get_environ(),
        last_modified=datetime.datetime(2020, 7, 11),
    )
    rv.close()
    assert "no-cache" in rv.headers["Cache-Control"]
    assert not rv.cache_control.public
    assert not rv.cache_control.max_age
    assert not rv.expires
    assert rv.status_code == 304


@pytest.mark.parametrize(("value", "public"), [(0, False), (60, True)])
def test_max_age(value, public):
    rv = send_file(txt_path, environ, max_age=value)
    rv.close()
    assert ("no-cache" in rv.headers["Cache-Control"]) != public
    assert rv.cache_control.public == public
    assert rv.cache_control.max_age == value
    assert rv.expires
    assert rv.status_code == 200
