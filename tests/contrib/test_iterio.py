from nose.tools import assert_raises
from werkzeug.contrib.iterio import IterIO


def test_itero():
    """Test the IterIO"""
    iterable = iter(["Hello", "World", "1", "2", "3"])
    io = IterIO(iterable)
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

    io = IterIO(iter(["Hello\n", "World!"]))
    assert io.readline() == 'Hello\n'
    assert io._buf == 'Hello\n'
    assert io.read() == 'World!'
    assert io._buf == 'Hello\nWorld!'
    assert io.tell() == 12
    io.seek(0)
    assert io.readlines() == ['Hello\n', 'World!']

    io = IterIO(iter(["foo\n", "bar"]))
    io.seek(-4, 2)
    assert io.read(4) == '\nbar'

    assert_raises(IOError, io.seek, 2, 100)
    io.close()
    assert_raises(ValueError, io.read)
