# -*- coding: utf-8 -*-
"""
    werkzeug.debug test
    ~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
import re
import sys
from werkzeug.debug.repr import debug_repr, DebugReprGenerator, dump, helper
from werkzeug.debug.console import HTMLStringO


def test_debug_repr():
    """Test the debug repr from the debug component"""
    assert debug_repr([]) == u'[]'
    assert debug_repr([1, 2]) == \
        u'[<span class="number">1</span>, <span class="number">2</span>]'
    assert debug_repr([1, 'test']) == \
        u'[<span class="number">1</span>, <span class="string">\'test\'</span>]'
    assert debug_repr([None]) == \
        u'[<span class="object">None</span>]'
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
    assert debug_repr({}) == u'{}'
    assert debug_repr({'foo': 42}) == \
        u'{<span class="pair"><span class="key"><span class="string">\'foo\''\
        u'</span></span>: <span class="value"><span class="number">42' \
        u'</span></span></span>}'
    assert debug_repr(dict(zip(range(10), [None] * 10))) == \
        u'{<span class="pair"><span class="key"><span class="number">0</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">1</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">2</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">3</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="extended"><span class="pair"><span class="key"><span class="number">4</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">5</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">6</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">7</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">8</span></span>: <span class="value"><span class="object">None</span></span></span>, <span class="pair"><span class="key"><span class="number">9</span></span>: <span class="value"><span class="object">None</span></span></span></span>}'
    assert debug_repr((1, 'zwei', u'drei')) ==\
        u'(<span class="number">1</span>, <span class="string">\'' \
        u'zwei\'</span>, <span class="string">u\'drei\'</span>)'

    class Foo(object):
        def __repr__(self):
            return '<Foo 42>'
    assert debug_repr(Foo()) == '<span class="object">&lt;Foo 42&gt;</span>'

    class MyList(list):
        pass
    assert debug_repr(MyList([1, 2])) == \
        u'<span class="module">test_debug.</span>MyList([' \
        u'<span class="number">1</span>, <span class="number">2</span>])'

    assert debug_repr(re.compile(r'foo\d')) == \
        u're.compile(<span class="string regex">r\'foo\\d\'</span>)'
    assert debug_repr(re.compile(ur'foo\d')) == \
        u're.compile(<span class="string regex">ur\'foo\\d\'</span>)'

    assert debug_repr(frozenset('x')) == \
        u'frozenset([<span class="string">\'x\'</span>])'
    assert debug_repr(set('x')) == \
        u'set([<span class="string">\'x\'</span>])'

    a = [1]
    a.append(a)
    assert debug_repr(a) == u'[<span class="number">1</span>, [...]]'

    class Foo(object):
        def __repr__(self):
            1/0

    assert debug_repr(Foo()) == \
        u'<span class="brokenrepr">&lt;broken repr (ZeroDivisionError: ' \
        u'integer division or modulo by zero)&gt;</span>'


def test_object_dumping():
    """Test debug object dumping to HTML"""
    class Foo(object):
        x = 42
        y = 23
        def __init__(self):
            self.z = 15

    drg = DebugReprGenerator()
    out = drg.dump_object(Foo())
    assert re.search('Details for test_debug.Foo object at', out)
    assert re.search('<th>x</th>.*<span class="number">42</span>(?s)', out)
    assert re.search('<th>y</th>.*<span class="number">23</span>(?s)', out)
    assert re.search('<th>z</th>.*<span class="number">15</span>(?s)', out)

    out = drg.dump_object({'x': 42, 'y': 23})
    assert re.search('Contents of', out)
    assert re.search('<th>x</th>.*<span class="number">42</span>(?s)', out)
    assert re.search('<th>y</th>.*<span class="number">23</span>(?s)', out)

    out = drg.dump_object({'x': 42, 'y': 23, 23: 11})
    assert not re.search('Contents of', out)

    out = drg.dump_locals({'x': 42, 'y': 23})
    assert re.search('Local variables in frame', out)
    assert re.search('<th>x</th>.*<span class="number">42</span>(?s)', out)
    assert re.search('<th>y</th>.*<span class="number">23</span>(?s)', out)


def test_debug_dump():
    """Test debug dump"""
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
    assert '<th>x</th>' in y
    assert '<th>old</th>' in y


def test_debug_help():
    """Test debug help"""
    old = sys.stdout
    sys.stdout = HTMLStringO()
    try:
        helper([1, 2, 3])
        x = sys.stdout.reset()
    finally:
        sys.stdout = old

    assert 'Help on list object' in x
    assert '__delitem__' in x
