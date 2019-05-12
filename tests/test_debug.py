# -*- coding: utf-8 -*-
"""
    tests.debug
    ~~~~~~~~~~~

    Tests some debug utilities.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import io
import re
import sys

import pytest
import requests

from werkzeug._compat import PY2
from werkzeug.debug import DebuggedApplication
from werkzeug.debug import get_machine_id
from werkzeug.debug.console import HTMLStringO
from werkzeug.debug.repr import debug_repr
from werkzeug.debug.repr import DebugReprGenerator
from werkzeug.debug.repr import dump
from werkzeug.debug.repr import helper
from werkzeug.debug.tbtools import Traceback
from werkzeug.test import Client
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


class TestDebugRepr(object):
    def test_basic_repr(self):
        assert debug_repr([]) == u"[]"
        assert (
            debug_repr([1, 2])
            == u'[<span class="number">1</span>, <span class="number">2</span>]'
        )
        assert (
            debug_repr([1, "test"])
            == u'[<span class="number">1</span>, <span class="string">\'test\'</span>]'
        )
        assert debug_repr([None]) == u'[<span class="object">None</span>]'

    def test_string_repr(self):
        assert debug_repr("") == u"<span class=\"string\">''</span>"
        assert debug_repr("foo") == u"<span class=\"string\">'foo'</span>"
        assert (
            debug_repr("s" * 80)
            == u'<span class="string">\''
            + "s" * 69
            + '<span class="extended">'
            + "s" * 11
            + "'</span></span>"
        )
        assert (
            debug_repr("<" * 80)
            == u'<span class="string">\''
            + "&lt;" * 69
            + '<span class="extended">'
            + "&lt;" * 11
            + "'</span></span>"
        )

    def test_string_subclass_repr(self):
        class Test(str):
            pass

        assert debug_repr(Test("foo")) == (
            u'<span class="module">tests.test_debug.</span>'
            u"Test(<span class=\"string\">'foo'</span>)"
        )

    @pytest.mark.skipif(not PY2, reason="u prefix on py2 only")
    def test_unicode_repr(self):
        assert debug_repr(u"foo") == u"<span class=\"string\">u'foo'</span>"

    @pytest.mark.skipif(PY2, reason="b prefix on py3 only")
    def test_bytes_repr(self):
        assert debug_repr(b"foo") == u"<span class=\"string\">b'foo'</span>"

    def test_sequence_repr(self):
        assert debug_repr(list(range(20))) == (
            u'[<span class="number">0</span>, <span class="number">1</span>, '
            u'<span class="number">2</span>, <span class="number">3</span>, '
            u'<span class="number">4</span>, <span class="number">5</span>, '
            u'<span class="number">6</span>, <span class="number">7</span>, '
            u'<span class="extended"><span class="number">8</span>, '
            u'<span class="number">9</span>, <span class="number">10</span>, '
            u'<span class="number">11</span>, <span class="number">12</span>, '
            u'<span class="number">13</span>, <span class="number">14</span>, '
            u'<span class="number">15</span>, <span class="number">16</span>, '
            u'<span class="number">17</span>, <span class="number">18</span>, '
            u'<span class="number">19</span></span>]'
        )

    def test_mapping_repr(self):
        assert debug_repr({}) == u"{}"
        assert debug_repr({"foo": 42}) == (
            u'{<span class="pair"><span class="key"><span class="string">\'foo\''
            u'</span></span>: <span class="value"><span class="number">42'
            u"</span></span></span>}"
        )
        assert debug_repr(dict(zip(range(10), [None] * 10))) == (
            u'{<span class="pair"><span class="key"><span class="number">0'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">1'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">2'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">3'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="extended">'
            u'<span class="pair"><span class="key"><span class="number">4'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">5'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">6'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">7'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">8'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span>, "
            u'<span class="pair"><span class="key"><span class="number">9'
            u'</span></span>: <span class="value"><span class="object">None'
            u"</span></span></span></span>}"
        )
        assert debug_repr((1, "zwei", u"drei")) == (
            u'(<span class="number">1</span>, <span class="string">\''
            u"zwei'</span>, <span class=\"string\">%s'drei'</span>)"
        ) % ("u" if PY2 else "")

    def test_custom_repr(self):
        class Foo(object):
            def __repr__(self):
                return "<Foo 42>"

        assert debug_repr(Foo()) == '<span class="object">&lt;Foo 42&gt;</span>'

    def test_list_subclass_repr(self):
        class MyList(list):
            pass

        assert debug_repr(MyList([1, 2])) == (
            u'<span class="module">tests.test_debug.</span>MyList(['
            u'<span class="number">1</span>, <span class="number">2</span>])'
        )

    def test_regex_repr(self):
        assert (
            debug_repr(re.compile(r"foo\d"))
            == u"re.compile(<span class=\"string regex\">r'foo\\d'</span>)"
        )
        # No ur'' in Py3
        # https://bugs.python.org/issue15096
        assert debug_repr(re.compile(u"foo\\d")) == (
            u"re.compile(<span class=\"string regex\">%sr'foo\\d'</span>)"
            % ("u" if PY2 else "")
        )

    def test_set_repr(self):
        assert (
            debug_repr(frozenset("x"))
            == u"frozenset([<span class=\"string\">'x'</span>])"
        )
        assert debug_repr(set("x")) == u"set([<span class=\"string\">'x'</span>])"

    def test_recursive_repr(self):
        a = [1]
        a.append(a)
        assert debug_repr(a) == u'[<span class="number">1</span>, [...]]'

    def test_broken_repr(self):
        class Foo(object):
            def __repr__(self):
                raise Exception("broken!")

        assert debug_repr(Foo()) == (
            u'<span class="brokenrepr">&lt;broken repr (Exception: '
            u"broken!)&gt;</span>"
        )


class Foo(object):
    x = 42
    y = 23

    def __init__(self):
        self.z = 15


class TestDebugHelpers(object):
    def test_object_dumping(self):
        drg = DebugReprGenerator()
        out = drg.dump_object(Foo())
        assert re.search("Details for tests.test_debug.Foo object at", out)
        assert re.search('<th>x.*<span class="number">42</span>', out, flags=re.DOTALL)
        assert re.search('<th>y.*<span class="number">23</span>', out, flags=re.DOTALL)
        assert re.search('<th>z.*<span class="number">15</span>', out, flags=re.DOTALL)

        out = drg.dump_object({"x": 42, "y": 23})
        assert re.search("Contents of", out)
        assert re.search('<th>x.*<span class="number">42</span>', out, flags=re.DOTALL)
        assert re.search('<th>y.*<span class="number">23</span>', out, flags=re.DOTALL)

        out = drg.dump_object({"x": 42, "y": 23, 23: 11})
        assert not re.search("Contents of", out)

        out = drg.dump_locals({"x": 42, "y": 23})
        assert re.search("Local variables in frame", out)
        assert re.search('<th>x.*<span class="number">42</span>', out, flags=re.DOTALL)
        assert re.search('<th>y.*<span class="number">23</span>', out, flags=re.DOTALL)

    def test_debug_dump(self):
        old = sys.stdout
        sys.stdout = HTMLStringO()
        try:
            dump([1, 2, 3])
            x = sys.stdout.reset()
            dump()
            y = sys.stdout.reset()
        finally:
            sys.stdout = old

        assert "Details for list object at" in x
        assert '<span class="number">1</span>' in x
        assert "Local variables in frame" in y
        assert "<th>x" in y
        assert "<th>old" in y

    def test_debug_help(self):
        old = sys.stdout
        sys.stdout = HTMLStringO()
        try:
            helper([1, 2, 3])
            x = sys.stdout.reset()
        finally:
            sys.stdout = old

        assert "Help on list object" in x
        assert "__delitem__" in x

    @pytest.mark.skipif(PY2, reason="Python 2 doesn't have chained exceptions.")
    def test_exc_divider_found_on_chained_exception(self):
        @Request.application
        def app(request):
            def do_something():
                raise ValueError("inner")

            try:
                do_something()
            except ValueError:
                raise KeyError("outer")

        debugged = DebuggedApplication(app)
        client = Client(debugged, Response)
        response = client.get("/")
        data = response.get_data(as_text=True)
        assert u'raise ValueError("inner")' in data
        assert u'<div class="exc-divider">' in data
        assert u'raise KeyError("outer")' in data


class TestTraceback(object):
    def test_log(self):
        try:
            1 / 0
        except ZeroDivisionError:
            traceback = Traceback(*sys.exc_info())

        buffer_ = io.BytesIO() if PY2 else io.StringIO()
        traceback.log(buffer_)
        assert buffer_.getvalue().strip() == traceback.plaintext.strip()

    def test_sourcelines_encoding(self):
        source = (
            u"# -*- coding: latin1 -*-\n\n"
            u"def foo():\n"
            u'    """höhö"""\n'
            u"    1 / 0\n"
            u"foo()"
        ).encode("latin1")
        code = compile(source, filename="lol.py", mode="exec")
        try:
            eval(code)
        except ZeroDivisionError:
            traceback = Traceback(*sys.exc_info())

        frames = traceback.frames
        assert len(frames) == 3
        assert frames[1].filename == "lol.py"
        assert frames[2].filename == "lol.py"

        class Loader(object):
            def get_source(self, module):
                return source

        frames[1].loader = frames[2].loader = Loader()
        assert frames[1].sourcelines == frames[2].sourcelines
        assert [line.code for line in frames[1].get_annotated_lines()] == [
            line.code for line in frames[2].get_annotated_lines()
        ]
        assert u"höhö" in frames[1].sourcelines[3]

    def test_filename_encoding(self, tmpdir, monkeypatch):
        moduledir = tmpdir.mkdir("föö")
        moduledir.join("bar.py").write("def foo():\n    1/0\n")
        monkeypatch.syspath_prepend(str(moduledir))

        import bar

        try:
            bar.foo()
        except ZeroDivisionError:
            traceback = Traceback(*sys.exc_info())

        assert u"föö" in u"\n".join(frame.render() for frame in traceback.frames)


def test_get_machine_id():
    rv = get_machine_id()
    assert isinstance(rv, bytes)


@pytest.mark.parametrize("crash", (True, False))
def test_basic(dev_server, crash):
    server = dev_server(
        """
    from werkzeug.debug import DebuggedApplication

    @DebuggedApplication
    def app(environ, start_response):
        if {crash}:
            1 / 0
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']
    """.format(
            crash=crash
        )
    )

    r = requests.get(server.url)
    assert r.status_code == 500 if crash else 200
    if crash:
        assert "The debugger caught an exception in your WSGI application" in r.text
    else:
        assert r.text == "hello"


@pytest.mark.skipif(PY2, reason="Python 2 doesn't have chained exceptions.")
@pytest.mark.timeout(2)
def test_chained_exception_cycle():
    try:
        try:
            raise ValueError()
        except ValueError:
            raise TypeError()
    except TypeError as e:
        # create a cycle and make it available outside the except block
        e.__context__.__context__ = error = e

    # if cycles aren't broken, this will time out
    tb = Traceback(TypeError, error, error.__traceback__)
    assert len(tb.groups) == 2


def test_non_hashable_exception():
    class MutableException(ValueError):
        __hash__ = None

    try:
        raise MutableException()
    except MutableException:
        # previously crashed: `TypeError: unhashable type 'MutableException'`
        Traceback(*sys.exc_info())
