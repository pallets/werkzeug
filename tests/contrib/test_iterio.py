# -*- coding: utf-8 -*-
"""
    tests.iterio
    ~~~~~~~~~~~~

    Tests the iterio object.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import pytest
from functools import partial

from tests import WerkzeugTests
from werkzeug.contrib.iterio import IterIO, greenlet


class IterOTestSuite(WerkzeugTests):

    def test_basic_native(self):
        io = IterIO(["Hello", "World", "1", "2", "3"])
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
        assert io.readline() == 'Hello\n'
        assert io._buf == 'Hello\n'
        assert io.read() == 'World!'
        assert io._buf == 'Hello\nWorld!'
        assert io.tell() == 12
        io.seek(0)
        self.assert_equal(io.readlines(), ['Hello\n', 'World!'])

        io = IterIO(['Line one\nLine ', 'two\nLine three'])
        self.assert_equal(list(io), ['Line one\n', 'Line two\n', 'Line three'])
        io = IterIO(iter('Line one\nLine two\nLine three'))
        self.assert_equal(list(io), ['Line one\n', 'Line two\n', 'Line three'])
        io = IterIO(['Line one\nL', 'ine', ' two', '\nLine three'])
        self.assert_equal(list(io), ['Line one\n', 'Line two\n', 'Line three'])

        io = IterIO(["foo\n", "bar"])
        io.seek(-4, 2)
        assert io.read(4) == '\nbar'

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
        assert io.readline() == b'Hello\n'
        assert io._buf == b'Hello\n'
        assert io.read() == b'World!'
        assert io._buf == b'Hello\nWorld!'
        assert io.tell() == 12
        io.seek(0)
        self.assert_equal(io.readlines(), [b'Hello\n', b'World!'])

        io = IterIO([b"foo\n", b"bar"])
        io.seek(-4, 2)
        assert io.read(4) == b'\nbar'

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
        assert io.readline() == u'Hello\n'
        assert io._buf == u'Hello\n'
        assert io.read() == u'World!'
        assert io._buf == u'Hello\nWorld!'
        assert io.tell() == 12
        io.seek(0)
        self.assert_equal(io.readlines(), [u'Hello\n', u'World!'])

        io = IterIO([u"foo\n", u"bar"])
        io.seek(-4, 2)
        assert io.read(4) == u'\nbar'

        pytest.raises(IOError, io.seek, 2, 100)
        io.close()
        pytest.raises(ValueError, io.read)

    def test_sentinel_cases(self):
        io = IterIO([])
        self.assert_strict_equal(io.read(), '')
        io = IterIO([], b'')
        self.assert_strict_equal(io.read(), b'')
        io = IterIO([], u'')
        self.assert_strict_equal(io.read(), u'')

        io = IterIO([])
        self.assert_strict_equal(io.read(), '')
        io = IterIO([b''])
        self.assert_strict_equal(io.read(), b'')
        io = IterIO([u''])
        self.assert_strict_equal(io.read(), u'')

        io = IterIO([])
        self.assert_strict_equal(io.readline(), '')
        io = IterIO([], b'')
        self.assert_strict_equal(io.readline(), b'')
        io = IterIO([], u'')
        self.assert_strict_equal(io.readline(), u'')

        io = IterIO([])
        self.assert_strict_equal(io.readline(), '')
        io = IterIO([b''])
        self.assert_strict_equal(io.readline(), b'')
        io = IterIO([u''])
        self.assert_strict_equal(io.readline(), u'')


@pytest.mark.skipif(greenlet is None, reason='Greenlet is not installed.')
class IterITestSuite(WerkzeugTests):
    def test_basic(self):
        def producer(out):
            out.write('1\n')
            out.write('2\n')
            out.flush()
            out.write('3\n')
        iterable = IterIO(producer)
        assert next(iterable) == '1\n2\n'
        assert next(iterable) == '3\n'
        pytest.raises(StopIteration, next, iterable)

    def test_sentinel_cases(self):
        def producer_dummy_flush(out):
            out.flush()
        iterable = IterIO(producer_dummy_flush)
        self.assert_strict_equal(next(iterable), '')

        def producer_empty(out):
            pass
        iterable = IterIO(producer_empty)
        pytest.raises(StopIteration, next, iterable)

        iterable = IterIO(producer_dummy_flush, b'')
        self.assert_strict_equal(next(iterable), b'')
        iterable = IterIO(producer_dummy_flush, u'')
        self.assert_strict_equal(next(iterable), u'')
