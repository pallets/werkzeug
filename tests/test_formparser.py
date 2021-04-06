import csv
import io
from os.path import dirname
from os.path import join

import pytest

from werkzeug import formparser
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser
from werkzeug.formparser import parse_form_data
from werkzeug.test import Client
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


@Request.application
def form_data_consumer(request):
    result_object = request.args["object"]
    if result_object == "text":
        return Response(repr(request.form["text"]))
    f = request.files[result_object]
    return Response(
        b"\n".join(
            (
                repr(f.filename).encode("ascii"),
                repr(f.name).encode("ascii"),
                repr(f.content_type).encode("ascii"),
                f.stream.read(),
            )
        )
    )


def get_contents(filename):
    with open(filename, "rb") as f:
        return f.read()


class TestFormParser:
    def test_limiting(self):
        data = b"foo=Hello+World&bar=baz"
        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="application/x-www-form-urlencoded",
            method="POST",
        )
        req.max_content_length = 400
        assert req.form["foo"] == "Hello World"

        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="application/x-www-form-urlencoded",
            method="POST",
        )
        req.max_form_memory_size = 7
        pytest.raises(RequestEntityTooLarge, lambda: req.form["foo"])

        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="application/x-www-form-urlencoded",
            method="POST",
        )
        req.max_form_memory_size = 400
        assert req.form["foo"] == "Hello World"

        data = (
            b"--foo\r\nContent-Disposition: form-field; name=foo\r\n\r\n"
            b"Hello World\r\n"
            b"--foo\r\nContent-Disposition: form-field; name=bar\r\n\r\n"
            b"bar=baz\r\n--foo--"
        )
        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        req.max_content_length = 4
        pytest.raises(RequestEntityTooLarge, lambda: req.form["foo"])

        # when the request entity is too large, the input stream should be
        # drained so that firefox (and others) do not report connection reset
        # when run through gunicorn
        # a sufficiently large stream is necessary for block-based reads
        input_stream = io.BytesIO(b"foo=" + b"x" * 128 * 1024)
        req = Request.from_values(
            input_stream=input_stream,
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        req.max_content_length = 4
        pytest.raises(RequestEntityTooLarge, lambda: req.form["foo"])
        # ensure that the stream is exhausted
        assert input_stream.read() == b""

        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        req.max_content_length = 400
        assert req.form["foo"] == "Hello World"

        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        req.max_form_memory_size = 7
        pytest.raises(RequestEntityTooLarge, lambda: req.form["foo"])

        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        req.max_form_memory_size = 400
        assert req.form["foo"] == "Hello World"

    def test_missing_multipart_boundary(self):
        data = (
            b"--foo\r\nContent-Disposition: form-field; name=foo\r\n\r\n"
            b"Hello World\r\n"
            b"--foo\r\nContent-Disposition: form-field; name=bar\r\n\r\n"
            b"bar=baz\r\n--foo--"
        )
        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data",
            method="POST",
        )
        assert req.form == {}

    def test_parse_form_data_put_without_content(self):
        # A PUT without a Content-Type header returns empty data

        # Both rfc1945 and rfc2616 (1.0 and 1.1) say "Any HTTP/[1.0/1.1] message
        # containing an entity-body SHOULD include a Content-Type header field
        # defining the media type of that body."  In the case where either
        # headers are omitted, parse_form_data should still work.
        env = create_environ("/foo", "http://example.org/", method="PUT")

        stream, form, files = formparser.parse_form_data(env)
        assert stream.read() == b""
        assert len(form) == 0
        assert len(files) == 0

    def test_parse_form_data_get_without_content(self):
        env = create_environ("/foo", "http://example.org/", method="GET")

        stream, form, files = formparser.parse_form_data(env)
        assert stream.read() == b""
        assert len(form) == 0
        assert len(files) == 0

    @pytest.mark.parametrize(
        ("no_spooled", "size"), ((False, 100), (False, 3000), (True, 100), (True, 3000))
    )
    def test_default_stream_factory(self, no_spooled, size, monkeypatch):
        if no_spooled:
            monkeypatch.setattr("werkzeug.formparser.SpooledTemporaryFile", None)

        data = b"a,b,c\n" * size
        req = Request.from_values(
            data={"foo": (io.BytesIO(data), "test.txt")}, method="POST"
        )
        file_storage = req.files["foo"]

        try:
            reader = csv.reader(io.TextIOWrapper(file_storage))
            # This fails if file_storage doesn't implement IOBase.
            # https://github.com/pallets/werkzeug/issues/1344
            # https://github.com/python/cpython/pull/3249
            assert sum(1 for _ in reader) == size
        finally:
            file_storage.close()

    def test_parse_bad_content_type(self):
        parser = FormDataParser()
        assert parser.parse("", "bad-mime-type", 0) == (
            "",
            MultiDict([]),
            MultiDict([]),
        )

    def test_parse_from_environ(self):
        parser = FormDataParser()
        stream, _, _ = parser.parse_from_environ({"wsgi.input": ""})
        assert stream is not None


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
class TestMultiPart:
    def test_basic(self):
        resources = join(dirname(__file__), "multipart")
        client = Client(form_data_consumer)

        repository = [
            (
                "firefox3-2png1txt",
                "---------------------------186454651713519341951581030105",
                [
                    ("anchor.png", "file1", "image/png", "file1.png"),
                    ("application_edit.png", "file2", "image/png", "file2.png"),
                ],
                "example text",
            ),
            (
                "firefox3-2pnglongtext",
                "---------------------------14904044739787191031754711748",
                [
                    ("accept.png", "file1", "image/png", "file1.png"),
                    ("add.png", "file2", "image/png", "file2.png"),
                ],
                "--long text\r\n--with boundary\r\n--lookalikes--",
            ),
            (
                "opera8-2png1txt",
                "----------zEO9jQKmLc2Cq88c23Dx19",
                [
                    ("arrow_branch.png", "file1", "image/png", "file1.png"),
                    ("award_star_bronze_1.png", "file2", "image/png", "file2.png"),
                ],
                "blafasel öäü",
            ),
            (
                "webkit3-2png1txt",
                "----WebKitFormBoundaryjdSFhcARk8fyGNy6",
                [
                    ("gtk-apply.png", "file1", "image/png", "file1.png"),
                    ("gtk-no.png", "file2", "image/png", "file2.png"),
                ],
                "this is another text with ümläüts",
            ),
            (
                "ie6-2png1txt",
                "---------------------------7d91b03a20128",
                [
                    ("file1.png", "file1", "image/x-png", "file1.png"),
                    ("file2.png", "file2", "image/x-png", "file2.png"),
                ],
                "ie6 sucks :-/",
            ),
        ]

        for name, boundary, files, text in repository:
            folder = join(resources, name)
            data = get_contents(join(folder, "request.http"))
            for filename, field, content_type, fsname in files:
                response = client.post(
                    f"/?object={field}",
                    data=data,
                    content_type=f'multipart/form-data; boundary="{boundary}"',
                    content_length=len(data),
                )
                lines = response.get_data().split(b"\n", 3)
                assert lines[0] == repr(filename).encode("ascii")
                assert lines[1] == repr(field).encode("ascii")
                assert lines[2] == repr(content_type).encode("ascii")
                assert lines[3] == get_contents(join(folder, fsname))
            response = client.post(
                "/?object=text",
                data=data,
                content_type=f'multipart/form-data; boundary="{boundary}"',
                content_length=len(data),
            )
            assert response.get_data() == repr(text).encode("utf-8")

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    def test_ie7_unc_path(self):
        client = Client(form_data_consumer)
        data_file = join(dirname(__file__), "multipart", "ie7_full_path_request.http")
        data = get_contents(data_file)
        boundary = "---------------------------7da36d1b4a0164"
        response = client.post(
            "/?object=cb_file_upload_multiple",
            data=data,
            content_type=f'multipart/form-data; boundary="{boundary}"',
            content_length=len(data),
        )
        lines = response.get_data().split(b"\n", 3)
        assert lines[0] == b"'Sellersburg Town Council Meeting 02-22-2010doc.doc'"

    def test_end_of_file(self):
        # This test looks innocent but it was actually timeing out in
        # the Werkzeug 0.5 release version (#394)
        data = (
            b"--foo\r\n"
            b'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"file contents and no end"
        )
        data = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        assert not data.files
        assert not data.form

    def test_file_no_content_type(self):
        data = (
            b"--foo\r\n"
            b'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n\r\n'
            b"file contents\r\n--foo--"
        )
        data = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        assert data.files["test"].filename == "test.txt"
        assert data.files["test"].read() == b"file contents"

    def test_extra_newline(self):
        # this test looks innocent but it was actually timeing out in
        # the Werkzeug 0.5 release version (#394)
        data = (
            b"\r\n\r\n--foo\r\n"
            b'Content-Disposition: form-data; name="foo"\r\n\r\n'
            b"a string\r\n"
            b"--foo--"
        )
        data = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        assert not data.files
        assert data.form["foo"] == "a string"

    def test_headers(self):
        data = (
            b"--foo\r\n"
            b'Content-Disposition: form-data; name="foo"; filename="foo.txt"\r\n'
            b"X-Custom-Header: blah\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"file contents, just the contents\r\n"
            b"--foo--"
        )
        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        foo = req.files["foo"]
        assert foo.mimetype == "text/plain"
        assert foo.mimetype_params == {"charset": "utf-8"}
        assert foo.headers["content-type"] == foo.content_type
        assert foo.content_type == "text/plain; charset=utf-8"
        assert foo.headers["x-custom-header"] == "blah"

    @pytest.mark.parametrize("ending", [b"\n", b"\r", b"\r\n"])
    def test_nonstandard_line_endings(self, ending: bytes):
        data = ending.join(
            (
                b"--foo",
                b"Content-Disposition: form-data; name=foo",
                b"",
                b"this is just bar",
                b"--foo",
                b"Content-Disposition: form-data; name=bar",
                b"",
                b"blafasel",
                b"--foo--",
            )
        )
        req = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        assert req.form["foo"] == "this is just bar"
        assert req.form["bar"] == "blafasel"

    def test_failures(self):
        def parse_multipart(stream, boundary, content_length):
            parser = formparser.MultiPartParser(content_length)
            return parser.parse(stream, boundary, content_length)

        data = b"--foo\r\n\r\nHello World\r\n--foo--"
        pytest.raises(ValueError, parse_multipart, io.BytesIO(data), b"foo", len(data))

        data = (
            b"--foo\r\nContent-Disposition: form-field; name=foo\r\n\r\nHello World\r\n"
        )
        pytest.raises(ValueError, parse_multipart, io.BytesIO(data), b"foo", len(data))

    def test_empty_multipart(self):
        environ = {}
        data = b"--boundary--"
        environ["REQUEST_METHOD"] = "POST"
        environ["CONTENT_TYPE"] = "multipart/form-data; boundary=boundary"
        environ["CONTENT_LENGTH"] = str(len(data))
        environ["wsgi.input"] = io.BytesIO(data)
        stream, form, files = parse_form_data(environ, silent=False)
        rv = stream.read()
        assert rv == b""
        assert form == MultiDict()
        assert files == MultiDict()


class TestMultiPartParser:
    def test_constructor_not_pass_stream_factory_and_cls(self):
        parser = formparser.MultiPartParser()

        assert parser.stream_factory is formparser.default_stream_factory
        assert parser.cls is MultiDict

    def test_constructor_pass_stream_factory_and_cls(self):
        def stream_factory():
            pass

        parser = formparser.MultiPartParser(stream_factory=stream_factory, cls=dict)

        assert parser.stream_factory is stream_factory
        assert parser.cls is dict

    def test_file_rfc2231_filename_continuations(self):
        data = (
            b"--foo\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Content-Disposition: form-data; name=rfc2231;\r\n"
            b"	filename*0*=ascii''a%20b%20;\r\n"
            b"	filename*1*=c%20d%20;\r\n"
            b'	filename*2="e f.txt"\r\n\r\n'
            b"file contents\r\n--foo--"
        )
        request = Request.from_values(
            input_stream=io.BytesIO(data),
            content_length=len(data),
            content_type="multipart/form-data; boundary=foo",
            method="POST",
        )
        assert request.files["rfc2231"].filename == "a b c d e f.txt"
        assert request.files["rfc2231"].read() == b"file contents"
