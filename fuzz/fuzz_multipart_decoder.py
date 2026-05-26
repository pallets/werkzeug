#!/usr/bin/env python3
"""
Fuzz harness for Werkzeug's sansio MultipartDecoder state machine.

This targets the lowest-level multipart parser - a streaming state machine
that processes raw bytes from untrusted HTTP request bodies. Bugs here could
cause parser confusion, OOB reads, ReDoS, or incorrect boundary detection,
affecting any application that accepts file uploads.

Attack surfaces:
- Boundary detection with crafted CRLF sequences
- Header parsing within parts (Content-Disposition, Content-Type)
- State machine transitions with malformed input
- Very large fields, zero-length parts, nested boundaries
"""
import sys
import atheris

with atheris.instrument_imports():
    from werkzeug.sansio.multipart import MultipartDecoder, NeedData, Epilogue
    from werkzeug.exceptions import RequestEntityTooLarge


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    if fdp.remaining_bytes() < 2:
        return

    # Generate a boundary (1-70 bytes, RFC 2046 limit is 70)
    boundary_len = fdp.ConsumeIntInRange(1, min(70, fdp.remaining_bytes()))
    raw_boundary = fdp.ConsumeBytes(boundary_len)
    # Keep only RFC-safe chars for boundary
    boundary = bytes(b if (0x20 <= b <= 0x7e and b not in b'"(),/:;<=>?@[]\\') else 0x61
                     for b in raw_boundary)
    if not boundary:
        boundary = b"x"

    # Remaining bytes are the raw multipart body - fully untrusted
    body = fdp.ConsumeBytes(fdp.remaining_bytes())

    try:
        decoder = MultipartDecoder(boundary, max_content_length=1024 * 1024)
        decoder.receive_data(body)
        decoder.receive_data(None)  # signal end of stream
        # Drain all events from the state machine
        while True:
            event = decoder.next_event()
            if isinstance(event, (NeedData, Epilogue)):
                break
    except RequestEntityTooLarge:
        pass  # expected when body exceeds max_content_length
    except (ValueError, TypeError, UnicodeError, KeyError, IndexError):
        pass  # expected parse failures
    except Exception:
        raise  # anything else = real bug


atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
