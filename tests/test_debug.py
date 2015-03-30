# -*- coding: utf-8 -*-
"""
    tests.debug
    ~~~~~~~~~~~

    Tests some debug utilities.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import sys
import re
import io

from werkzeug.debug.repr import debug_repr, DebugReprGenerator, \
    dump, helper
from werkzeug.debug.console import HTMLStringO
from werkzeug.debug.tbtools import Traceback
from werkzeug._compat import PY2


class TestDebugRepr(object):

    def test_basic_repr(self):
        assert debug_repr([]) == u'[]'
        assert debug_repr([1, 2]) == \
            u'[<span class="number">1</span>, <span class="number">2</span>]'
        assert debug_repr([1, 'test']) == \
            u'[<span class="number">1</span>, <span class="string">\'test\'</span>]'
        assert debug_repr([None]) == \
            u'[<span class="object">None</span>]'

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
        assert debug_repr({}) == u'{}'
        assert debug_repr({'foo': 42}) == (
            u'{<span class="pair"><span class="key"><span class="string">\'foo\''
            u'</span></span>: <span class="value"><span class="number">42'
            u'</span></span></span>}'
        )
        assert debug_repr(dict(zip(range(10), [None] * 10))) == (
            u'{<span class="pair"><span class="key"><span class="number">0</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">1</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">2</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">3</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="extended"><span class="pair"><span class="key"><span class="number">4</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">5</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">6</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">7</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">8</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">9</span></span>: <span class="value"><span class="object">None</span></span></span></span>}'  # noqa
        )
        assert debug_repr((1, 'zwei', u'drei')) == (
            u'(<span class="number">1</span>, <span class="string">\''
            u'zwei\'</span>, <span class="string">%s\'drei\'</span>)'
        ) % ('u' if PY2 else '')

    def test_custom_repr(self):
        class Foo(object):

            def __repr__(self):
                return '<Foo 42>'
        assert debug_repr(Foo()) == \
            '<span class="object">&lt;Foo 42&gt;</span>'

    def test_list_subclass_repr(self):
        class MyList(list):
            pass
        assert debug_repr(MyList([1, 2])) == (
            u'<span class="module">tests.test_debug.</span>MyList(['
            u'<span class="number">1</span>, <span class="number">2</span>])'
        )

    def test_regex_repr(self):
        assert debug_repr(re.compile(r'foo\d')) == \
            u're.compile(<span class="string regex">r\'foo\\d\'</span>)'
        # No ur'' in Py3
        # http://bugs.python.org/issue15096
        assert debug_repr(re.compile(u'foo\\d')) == (
            u're.compile(<span class="string regex">%sr\'foo\\d\'</span>)' %
            ('u' if PY2 else '')
        )

    def test_set_repr(self):
        assert debug_repr(frozenset('x')) == \
            u'frozenset([<span class="string">\'x\'</span>])'
        assert debug_repr(set('x')) == \
            u'set([<span class="string">\'x\'</span>])'

    def test_recursive_repr(self):
        a = [1]
        a.append(a)
        assert debug_repr(a) == u'[<span class="number">1</span>, [...]]'

    def test_broken_repr(self):
        class Foo(object):

            def __repr__(self):
                raise Exception('broken!')

        assert debug_repr(Foo()) == (
            u'<span class="brokenrepr">&lt;broken repr (Exception: '
            u'broken!)&gt;</span>'
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
        assert re.search('Details for tests.test_debug.Foo object at', out)
        assert re.search('<th>x.*<span class="number">42</span>(?s)', out)
        assert re.search('<th>y.*<span class="number">23</span>(?s)', out)
        assert re.search('<th>z.*<span class="number">15</span>(?s)', out)

        out = drg.dump_object({'x': 42, 'y': 23})
        assert re.search('Contents of', out)
        assert re.search('<th>x.*<span class="number">42</span>(?s)', out)
        assert re.search('<th>y.*<span class="number">23</span>(?s)', out)

        out = drg.dump_object({'x': 42, 'y': 23, 23: 11})
        assert not re.search('Contents of', out)

        out = drg.dump_locals({'x': 42, 'y': 23})
        assert re.search('Local variables in frame', out)
        assert re.search('<th>x.*<span class="number">42</span>(?s)', out)
        assert re.search('<th>y.*<span class="number">23</span>(?s)', out)

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

        assert 'Details for list object at' in x
        assert '<span class="number">1</span>' in x
        assert 'Local variables in frame' in y
        assert '<th>x' in y
        assert '<th>old' in y

    def test_debug_help(self):
        old = sys.stdout
        sys.stdout = HTMLStringO()
        try:
            helper([1, 2, 3])
            x = sys.stdout.reset()
        finally:
            sys.stdout = old

        assert 'Help on list object' in x
        assert '__delitem__' in x


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
        source = (u'# -*- coding: latin1 -*-\n\n'
                  u'def foo():\n'
                  u'    """höhö"""\n'
                  u'    1 / 0\n'
                  u'foo()').encode('latin1')
        code = compile(source, filename='lol.py', mode='exec')
        try:
            eval(code)
        except ZeroDivisionError:
            traceback = Traceback(*sys.exc_info())

        frames = traceback.frames
        assert len(frames) == 3
        assert frames[1].filename == 'lol.py'
        assert frames[2].filename == 'lol.py'

        class Loader(object):

            def get_source(self, module):
                return source

        frames[1].loader = frames[2].loader = Loader()
        assert frames[1].sourcelines == frames[2].sourcelines
        assert [line.code for line in frames[1].get_annotated_lines()] == \
            [line.code for line in frames[2].get_annotated_lines()]
        assert u'höhö' in frames[1].sourcelines[3]

    def test_filename_encoding(self, tmpdir, monkeypatch):
        moduledir = tmpdir.mkdir('föö')
        moduledir.join('bar.py').write('def foo():\n    1/0\n')
        monkeypatch.syspath_prepend(str(moduledir))

        import bar

        try:
            bar.foo()
        except ZeroDivisionError:
            traceback = Traceback(*sys.exc_info())

        assert u'föö' in u'\n'.join(frame.render() for frame in traceback.frames)
