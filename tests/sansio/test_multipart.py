import pytest

from werkzeug.datastructures import Headers
from werkzeug.sansio.multipart import Data
from werkzeug.sansio.multipart import Epilogue
from werkzeug.sansio.multipart import Field
from werkzeug.sansio.multipart import File
from werkzeug.sansio.multipart import MultipartDecoder
from werkzeug.sansio.multipart import MultipartEncoder
from werkzeug.sansio.multipart import NeedData
from werkzeug.sansio.multipart import Preamble


def test_decoder_simple() -> None:
    boundary = b"---------------------------9704338192090380615194531385$"
    decoder = MultipartDecoder(boundary)
    data = """
-----------------------------9704338192090380615194531385$
Content-Disposition: form-data; name="fname"

ß∑œß∂ƒå∂
-----------------------------9704338192090380615194531385$
Content-Disposition: form-data; name="lname"; filename="bob"

asdasd
-----------------------------9704338192090380615194531385$--
    """.replace("\n", "\r\n").encode()
    decoder.receive_data(data)
    decoder.receive_data(None)
    events = [decoder.next_event()]
    while not isinstance(events[-1], Epilogue):
        events.append(decoder.next_event())
    assert events == [
        Preamble(data=b""),
        Field(
            name="fname",
            headers=Headers([("Content-Disposition", 'form-data; name="fname"')]),
        ),
        Data(data="ß∑œß∂ƒå∂".encode(), more_data=False),
        File(
            name="lname",
            filename="bob",
            headers=Headers(
                [("Content-Disposition", 'form-data; name="lname"; filename="bob"')]
            ),
        ),
        Data(data=b"asdasd", more_data=False),
        Epilogue(data=b"    "),
    ]
    encoder = MultipartEncoder(boundary)
    result = b""
    for event in events:
        result += encoder.send_event(event)
    assert data == result


@pytest.mark.parametrize(
    "data_start",
    [
        b"A",
        b"\n",
        b"\r",
        b"\r\n",
        b"\n\r",
        b"A\n",
        b"A\r",
        b"A\r\n",
        b"A\n\r",
    ],
)
@pytest.mark.parametrize("data_end", [b"", b"\r\n--foo"])
def test_decoder_data_start_with_different_newline_positions(
    data_start: bytes, data_end: bytes
) -> None:
    boundary = b"foo"
    data = (
        b"\r\n--foo\r\n"
        b'Content-Disposition: form-data; name="test"; filename="testfile"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        b"" + data_start + b"\r\nBCDE" + data_end
    )
    decoder = MultipartDecoder(boundary)
    decoder.receive_data(data)
    events = [decoder.next_event()]
    # We want to check up to data start event
    while not isinstance(events[-1], Data):
        events.append(decoder.next_event())

    expected = data_start

    if data_end == b"":
        # a split \r\n is deferred to the next event
        if expected[-1] == 0x0D:
            expected = expected[:-1]
    else:
        expected += b"\r\nBCDE"

    assert events == [
        Preamble(data=b""),
        File(
            name="test",
            filename="testfile",
            headers=Headers(
                [
                    (
                        "Content-Disposition",
                        'form-data; name="test"; filename="testfile"',
                    ),
                    ("Content-Type", "application/octet-stream"),
                ]
            ),
        ),
        Data(data=expected, more_data=True),
    ]


def test_chunked_boundaries() -> None:
    boundary = b"--boundary"
    decoder = MultipartDecoder(boundary)
    decoder.receive_data(b"--")
    assert isinstance(decoder.next_event(), NeedData)
    decoder.receive_data(b"--boundary\r\n")
    assert isinstance(decoder.next_event(), Preamble)
    decoder.receive_data(b"Content-Disposition: form-data;")
    assert isinstance(decoder.next_event(), NeedData)
    decoder.receive_data(b'name="fname"\r\n\r\n')
    assert isinstance(decoder.next_event(), Field)
    decoder.receive_data(b"longer than the boundary")
    assert isinstance(decoder.next_event(), Data)
    decoder.receive_data(b"also longer, but includes a linebreak\r\n--")
    assert isinstance(decoder.next_event(), Data)
    assert isinstance(decoder.next_event(), NeedData)
    decoder.receive_data(b"--boundary--\r\n")
    event = decoder.next_event()
    assert isinstance(event, Data)
    assert not event.more_data
    decoder.receive_data(None)
    assert isinstance(decoder.next_event(), Epilogue)


def test_empty_field() -> None:
    boundary = b"foo"
    decoder = MultipartDecoder(boundary)
    data = """
--foo
Content-Disposition: form-data; name="text"
Content-Type: text/plain; charset="UTF-8"

Some Text
--foo
Content-Disposition: form-data; name="empty"
Content-Type: text/plain; charset="UTF-8"

--foo--
    """.replace("\n", "\r\n").encode()
    decoder.receive_data(data)
    decoder.receive_data(None)
    events = [decoder.next_event()]
    while not isinstance(events[-1], Epilogue):
        events.append(decoder.next_event())
    assert events == [
        Preamble(data=b""),
        Field(
            name="text",
            headers=Headers(
                [
                    ("Content-Disposition", 'form-data; name="text"'),
                    ("Content-Type", 'text/plain; charset="UTF-8"'),
                ]
            ),
        ),
        Data(data=b"Some Text", more_data=False),
        Field(
            name="empty",
            headers=Headers(
                [
                    ("Content-Disposition", 'form-data; name="empty"'),
                    ("Content-Type", 'text/plain; charset="UTF-8"'),
                ]
            ),
        ),
        Data(data=b"", more_data=False),
        Epilogue(data=b"    "),
    ]
    encoder = MultipartEncoder(boundary)
    result = b""
    for event in events:
        result += encoder.send_event(event)
    assert data == result
