import pytest

from io import BytesIO
from sys import maxint
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser, default_stream_factory


class TestFormDataParser(object):
    """
    Testcases for `FormDataParser`
    """

    @pytest.mark.parametrize('size,expected', [
        (-1, BytesIO),
        (0, BytesIO),
        (1024 * 500, BytesIO),
        (1024 * 501, file),
        (maxint, file),
    ])
    def test_default_stream_factory(self, size, expected):
        assert isinstance(default_stream_factory(size, '', ''), expected)

    def test_parse_bad_content_type(self):
        parser = FormDataParser()
        assert parser.parse('', 'bad-mime-type', 0) == \
            ('', MultiDict([]), MultiDict([]))

    def test_parse_from_environ(self):
        parser = FormDataParser()
        stream, _, _ = parser.parse_from_environ({'wsgi.input': ''})
        assert stream is not None

    def test_parse_content_too_large(self):
        parser = FormDataParser()
        parser.max_content_length = 1
        stream = default_stream_factory(100, '', '')
        with pytest.raises(RequestEntityTooLarge):
            parser.parse(stream, 'application/x-url-encoded', 10)

    def test_parse_form_too_large(self):
        parser = FormDataParser()
        parser.max_form_memory_size = 1
        stream = default_stream_factory(100, '', '')
        with pytest.raises(RequestEntityTooLarge):
            parser.parse(stream, 'application/x-url-encoded', 10)

    def test_parse_url_encoded_content_type(self):
        url_encoded_form = 'a=b&c=d'
        expected_form = {
            'a': ['b'],
            'c': ['d']
        }
        parser = FormDataParser()
        stream = default_stream_factory(100, '', '')
        stream.write(url_encoded_form)
        stream.seek(0)
        s, form, _ = parser.parse(stream, 'application/x-url-encoded', 0)
        assert stream == s
        assert dict(form) == expected_form
