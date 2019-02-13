# -*- coding: utf-8 -*-
"""
    tests.iterio
    ~~~~~~~~~~~~

    Tests the iterio object.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import pytest

from .. import strict_eq
from werkzeug.contrib.iterio import greenlet
from werkzeug.contrib.iterio import IterIO


class TestIterO(object):
    def test_basic_native(self):
        io = IterIO(["Hello", "World", "1", "2", "3"])
        io.seek(0)
        assert io.tell() == 0
        assert io.read(2) == "He"
        assert io.tell() == 2
        assert io.read(3) == "llo"
        assert io.tell() == 5
        io.seek(0)
        assert io.read(5) == "Hello"
        assert io.tell() == 5
        assert io._buf == "Hello"
        assert io.read() == "World123"
        assert io.tell() == 13
        io.close()
        assert io.closed

        io = IterIO(["Hello\n", "World!"])
        assert io.readline() == "Hello\n"
        assert io._buf == "Hello\n"
        assert io.read() == "World!"
        assert io._buf == "Hello\nWorld!"
        assert io.tell() == 12
        io.seek(0)
        assert io.readlines() == ["Hello\n", "World!"]

        io = IterIO(["Line one\nLine ", "two\nLine three"])
        assert list(io) == ["Line one\n", "Line two\n", "Line three"]
        io = IterIO(iter("Line one\nLine two\nLine three"))
        assert list(io) == ["Line one\n", "Line two\n", "Line three"]
        io = IterIO(["Line one\nL", "ine", " two", "\nLine three"])
        assert list(io) == ["Line one\n", "Line two\n", "Line three"]

        io = IterIO(["foo\n", "bar"])
        io.seek(-4, 2)
        assert io.read(4) == "\nbar"

        pytest.raises(IOError, io.seek, 2, 100)
        io.close()
        pytest.raises(ValueError, io.read)

    def test_basic_bytes(self):
        io = IterIO([b"Hello", b"World", b"1", b"2", b"3"])
        assert io.tell() == 0
        assert io.read(2) == b"He"
        assert io.tell() == 2
        assert io.read(3) == b"llo"
        assert io.tell() == 5
        io.seek(0)
        assert io.read(5) == b"Hello"
        assert io.tell() == 5
        assert io._buf == b"Hello"
        assert io.read() == b"World123"
        assert io.tell() == 13
        io.close()
        assert io.closed

        io = IterIO([b"Hello\n", b"World!"])
        assert io.readline() == b"Hello\n"
        assert io._buf == b"Hello\n"
        assert io.read() == b"World!"
        assert io._buf == b"Hello\nWorld!"
        assert io.tell() == 12
        io.seek(0)
        assert io.readlines() == [b"Hello\n", b"World!"]

        io = IterIO([b"foo\n", b"bar"])
        io.seek(-4, 2)
        assert io.read(4) == b"\nbar"

        pytest.raises(IOError, io.seek, 2, 100)
        io.close()
        pytest.raises(ValueError, io.read)

    def test_basic_unicode(self):
        io = IterIO([u"Hello", u"World", u"1", u"2", u"3"])
        assert io.tell() == 0
        assert io.read(2) == u"He"
        assert io.tell() == 2
        assert io.read(3) == u"llo"
        assert io.tell() == 5
        io.seek(0)
        assert io.read(5) == u"Hello"
        assert io.tell() == 5
        assert io._buf == u"Hello"
        assert io.read() == u"World123"
        assert io.tell() == 13
        io.close()
        assert io.closed

        io = IterIO([u"Hello\n", u"World!"])
        assert io.readline() == u"Hello\n"
        assert io._buf == u"Hello\n"
        assert io.read() == u"World!"
        assert io._buf == u"Hello\nWorld!"
        assert io.tell() == 12
        io.seek(0)
        assert io.readlines() == [u"Hello\n", u"World!"]

        io = IterIO([u"foo\n", u"bar"])
        io.seek(-4, 2)
        assert io.read(4) == u"\nbar"

        pytest.raises(IOError, io.seek, 2, 100)
        io.close()
        pytest.raises(ValueError, io.read)

    def test_sentinel_cases(self):
        io = IterIO([])
        strict_eq(io.read(), "")
        io = IterIO([], b"")
        strict_eq(io.read(), b"")
        io = IterIO([], u"")
        strict_eq(io.read(), u"")

        io = IterIO([])
        strict_eq(io.read(), "")
        io = IterIO([b""])
        strict_eq(io.read(), b"")
        io = IterIO([u""])
        strict_eq(io.read(), u"")

        io = IterIO([])
        strict_eq(io.readline(), "")
        io = IterIO([], b"")
        strict_eq(io.readline(), b"")
        io = IterIO([], u"")
        strict_eq(io.readline(), u"")

        io = IterIO([])
        strict_eq(io.readline(), "")
        io = IterIO([b""])
        strict_eq(io.readline(), b"")
        io = IterIO([u""])
        strict_eq(io.readline(), u"")


@pytest.mark.skipif(greenlet is None, reason="Greenlet is not installed.")
class TestIterI(object):
    def test_basic(self):
        def producer(out):
            out.write("1\n")
            out.write("2\n")
            out.flush()
            out.write("3\n")

        iterable = IterIO(producer)
        assert next(iterable) == "1\n2\n"
        assert next(iterable) == "3\n"
        pytest.raises(StopIteration, next, iterable)

    def test_sentinel_cases(self):
        def producer_dummy_flush(out):
            out.flush()

        iterable = IterIO(producer_dummy_flush)
        strict_eq(next(iterable), "")

        def producer_empty(out):
            pass

        iterable = IterIO(producer_empty)
        pytest.raises(StopIteration, next, iterable)

        iterable = IterIO(producer_dummy_flush, b"")
        strict_eq(next(iterable), b"")
        iterable = IterIO(producer_dummy_flush, u"")
        strict_eq(next(iterable), u"")
