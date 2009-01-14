# -*- coding: utf-8 -*-
"""
    werkzeug.templates test
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD license.
"""
from nose.tools import assert_raises

from werkzeug.utils import MultiDict
from werkzeug.templates import Template


def test_interpolation():
    """Template variable interpolation"""
    t = Template('\n'.join([
        '$string',
        '${", ".join(string.upper().split(" AND "))}',
        '$string.replace("foo", "bar").title()',
        '${string}s',
        '${1, 2, 3}',
        '$string[0:3][::-1]'
    ]))
    assert t.render(string='foo and blah').splitlines() == [
        'foo and blah',
        'FOO, BLAH',
        'Bar And Blah',
        'foo and blahs',
        '(1, 2, 3)',
        'oof'
    ]


def test_while():
    """Template while loop"""
    t = Template('<%py idx = 0 %><% while idx < 10 %>x<%py idx += 1 %><% endwhile %>')
    assert t.render() == 'x' * 10


def test_for():
    """Template for loop"""
    t = Template('<% for i in range(10) %>[$i]<% endfor %>')
    assert t.render() == ''.join(['[%s]' % i for i in xrange(10)])


def test_if():
    """Template if condition"""
    t = Template('<% if idx == 1 %>ONE<% elif idx == 2 %>TWO<% elif '
                 'idx == 3 %>THREE<% else %>OMGWTF<% endif %>')
    assert t.render(idx=0) == 'OMGWTF'
    assert t.render(idx=1) == 'ONE'
    assert t.render(idx=2) == 'TWO'
    assert t.render(idx=3) == 'THREE'


def test_break():
    """Template brake statement"""
    t = Template('<% for i in xrange(5) %><%py break %>$i<% endfor %>')
    assert t.render() == ''


def test_continue():
    """Template continue statement"""
    t = Template('<% for i in xrange(10) %><% if i % 2 == 0 %>'
                 '<%py continue %><% endif %>$i<% endfor %>')
    assert t.render() == '13579'


def test_print():
    """Template print helper"""
    t = Template('1 <%py print "2", %>3')
    t.render() == '1 2 3'


def test_code():
    """Template code block"""
    t = Template('''<%py
        a = 'A'
        b = 'B'
    %>$a$b''')
    assert t.render() == 'AB'


def test_undefined():
    """Template undefined behavior"""
    t = Template('<% for item in seq %>$item<% endfor %>$missing')
    assert t.render() == ''


def test_unicode():
    """Template unicode modes"""
    t = Template(u'öäü$szlig')
    assert t.render(szlig='ß') == u'öäüß'
    t = Template(u'öäü$szlig', unicode_mode=False, encoding='iso-8859-15')
    assert t.render(szlig='\xdf') == '\xf6\xe4\xfc\xdf'


def test_nl_trim():
    """Template newline trimming"""
    t = Template('<% if 1 %>1<% endif %>\n2')
    assert t.render() == '12'


def test_multidict():
    """Template multidict behavior"""
    t = Template('$a|$b')
    assert t.render(MultiDict(dict(
        a=[1, 2],
        b=2
    ))) == '1|2'
