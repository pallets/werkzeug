# -*- coding: utf-8 -*-
"""
    tests.utils
    ~~~~~~~~~~~

    General utilities.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import inspect
from datetime import datetime

import pytest

from werkzeug import utils
from werkzeug._compat import text_type
from werkzeug.datastructures import Headers
from werkzeug.http import http_date
from werkzeug.http import parse_date
from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse


def test_redirect():
    resp = utils.redirect(u"/füübär")
    assert b"/f%C3%BC%C3%BCb%C3%A4r" in resp.get_data()
    assert resp.headers["Location"] == "/f%C3%BC%C3%BCb%C3%A4r"
    assert resp.status_code == 302

    resp = utils.redirect(u"http://☃.net/", 307)
    assert b"http://xn--n3h.net/" in resp.get_data()
    assert resp.headers["Location"] == "http://xn--n3h.net/"
    assert resp.status_code == 307

    resp = utils.redirect("http://example.com/", 305)
    assert resp.headers["Location"] == "http://example.com/"
    assert resp.status_code == 305


def test_redirect_xss():
    location = 'http://example.com/?xss="><script>alert(1)</script>'
    resp = utils.redirect(location)
    assert b"<script>alert(1)</script>" not in resp.get_data()

    location = 'http://example.com/?xss="onmouseover="alert(1)'
    resp = utils.redirect(location)
    assert (
        b'href="http://example.com/?xss="onmouseover="alert(1)"' not in resp.get_data()
    )


def test_redirect_with_custom_response_class():
    class MyResponse(BaseResponse):
        pass

    location = "http://example.com/redirect"
    resp = utils.redirect(location, Response=MyResponse)

    assert isinstance(resp, MyResponse)
    assert resp.headers["Location"] == location


def test_cached_property():
    foo = []

    class A(object):
        def prop(self):
            foo.append(42)
            return 42

        prop = utils.cached_property(prop)

    a = A()
    p = a.prop
    q = a.prop
    assert p == q == 42
    assert foo == [42]

    foo = []

    class A(object):
        def _prop(self):
            foo.append(42)
            return 42

        prop = utils.cached_property(_prop, name="prop")
        del _prop

    a = A()
    p = a.prop
    q = a.prop
    assert p == q == 42
    assert foo == [42]


def test_can_set_cached_property():
    class A(object):
        @utils.cached_property
        def _prop(self):
            return "cached_property return value"

    a = A()
    a._prop = "value"
    assert a._prop == "value"


def test_inspect_treats_cached_property_as_property():
    class A(object):
        @utils.cached_property
        def _prop(self):
            return "cached_property return value"

    attrs = inspect.classify_class_attrs(A)
    for attr in attrs:
        if attr.name == "_prop":
            break
    assert attr.kind == "property"


def test_environ_property():
    class A(object):
        environ = {"string": "abc", "number": "42"}

        string = utils.environ_property("string")
        missing = utils.environ_property("missing", "spam")
        read_only = utils.environ_property("number")
        number = utils.environ_property("number", load_func=int)
        broken_number = utils.environ_property("broken_number", load_func=int)
        date = utils.environ_property(
            "date", None, parse_date, http_date, read_only=False
        )
        foo = utils.environ_property("foo")

    a = A()
    assert a.string == "abc"
    assert a.missing == "spam"

    def test_assign():
        a.read_only = "something"

    pytest.raises(AttributeError, test_assign)
    assert a.number == 42
    assert a.broken_number is None
    assert a.date is None
    a.date = datetime(2008, 1, 22, 10, 0, 0, 0)
    assert a.environ["date"] == "Tue, 22 Jan 2008 10:00:00 GMT"


def test_escape():
    class Foo(str):
        def __html__(self):
            return text_type(self)

    assert utils.escape(None) == ""
    assert utils.escape(42) == "42"
    assert utils.escape("<>") == "&lt;&gt;"
    assert utils.escape('"foo"') == "&quot;foo&quot;"
    assert utils.escape(Foo("<foo>")) == "<foo>"


def test_unescape():
    assert utils.unescape("&lt;&auml;&gt;") == u"<ä>"


def test_import_string():
    from datetime import date
    from werkzeug.debug import DebuggedApplication

    assert utils.import_string("datetime.date") is date
    assert utils.import_string(u"datetime.date") is date
    assert utils.import_string("datetime:date") is date
    assert utils.import_string("XXXXXXXXXXXX", True) is None
    assert utils.import_string("datetime.XXXXXXXXXXXX", True) is None
    assert (
        utils.import_string(u"werkzeug.debug.DebuggedApplication")
        is DebuggedApplication
    )
    pytest.raises(ImportError, utils.import_string, "XXXXXXXXXXXXXXXX")
    pytest.raises(ImportError, utils.import_string, "datetime.XXXXXXXXXX")


def test_import_string_provides_traceback(tmpdir, monkeypatch):
    monkeypatch.syspath_prepend(str(tmpdir))
    # Couple of packages
    dir_a = tmpdir.mkdir("a")
    dir_b = tmpdir.mkdir("b")
    # Totally packages, I promise
    dir_a.join("__init__.py").write("")
    dir_b.join("__init__.py").write("")
    # 'aa.a' that depends on 'bb.b', which in turn has a broken import
    dir_a.join("aa.py").write("from b import bb")
    dir_b.join("bb.py").write("from os import a_typo")

    # Do we get all the useful information in the traceback?
    with pytest.raises(ImportError) as baz_exc:
        utils.import_string("a.aa")
    traceback = "".join((str(line) for line in baz_exc.traceback))
    assert "bb.py':1" in traceback  # a bit different than typical python tb
    assert "from os import a_typo" in traceback


def test_import_string_attribute_error(tmpdir, monkeypatch):
    monkeypatch.syspath_prepend(str(tmpdir))
    tmpdir.join("foo_test.py").write("from bar_test import value")
    tmpdir.join("bar_test.py").write('raise AttributeError("screw you!")')
    with pytest.raises(AttributeError) as foo_exc:
        utils.import_string("foo_test")
    assert "screw you!" in str(foo_exc)

    with pytest.raises(AttributeError) as bar_exc:
        utils.import_string("bar_test")
    assert "screw you!" in str(bar_exc)


def test_find_modules():
    assert list(utils.find_modules("werkzeug.debug")) == [
        "werkzeug.debug.console",
        "werkzeug.debug.repr",
        "werkzeug.debug.tbtools",
    ]


def test_html_builder():
    html = utils.html
    xhtml = utils.xhtml
    assert html.p("Hello World") == "<p>Hello World</p>"
    assert html.a("Test", href="#") == '<a href="#">Test</a>'
    assert html.br() == "<br>"
    assert xhtml.br() == "<br />"
    assert html.img(src="foo") == '<img src="foo">'
    assert xhtml.img(src="foo") == '<img src="foo" />'
    assert html.html(
        html.head(html.title("foo"), html.script(type="text/javascript"))
    ) == (
        '<html><head><title>foo</title><script type="text/javascript">'
        "</script></head></html>"
    )
    assert html("<foo>") == "&lt;foo&gt;"
    assert html.input(disabled=True) == "<input disabled>"
    assert xhtml.input(disabled=True) == '<input disabled="disabled" />'
    assert html.input(disabled="") == "<input>"
    assert xhtml.input(disabled="") == "<input />"
    assert html.input(disabled=None) == "<input>"
    assert xhtml.input(disabled=None) == "<input />"
    assert (
        html.script('alert("Hello World");') == '<script>alert("Hello World");</script>'
    )
    assert (
        xhtml.script('alert("Hello World");')
        == '<script>/*<![CDATA[*/alert("Hello World");/*]]>*/</script>'
    )


def test_validate_arguments():
    def take_none():
        pass

    def take_two(a, b):
        pass

    def take_two_one_default(a, b=0):
        pass

    assert utils.validate_arguments(take_two, (1, 2), {}) == ((1, 2), {})
    assert utils.validate_arguments(take_two, (1,), {"b": 2}) == ((1, 2), {})
    assert utils.validate_arguments(take_two_one_default, (1,), {}) == ((1, 0), {})
    assert utils.validate_arguments(take_two_one_default, (1, 2), {}) == ((1, 2), {})

    pytest.raises(
        utils.ArgumentValidationError, utils.validate_arguments, take_two, (), {}
    )

    assert utils.validate_arguments(take_none, (1, 2), {"c": 3}) == ((), {})
    pytest.raises(
        utils.ArgumentValidationError,
        utils.validate_arguments,
        take_none,
        (1,),
        {},
        drop_extra=False,
    )
    pytest.raises(
        utils.ArgumentValidationError,
        utils.validate_arguments,
        take_none,
        (),
        {"a": 1},
        drop_extra=False,
    )


def test_header_set_duplication_bug():
    headers = Headers([("Content-Type", "text/html"), ("Foo", "bar"), ("Blub", "blah")])
    headers["blub"] = "hehe"
    headers["blafasel"] = "humm"
    assert headers == Headers(
        [
            ("Content-Type", "text/html"),
            ("Foo", "bar"),
            ("blub", "hehe"),
            ("blafasel", "humm"),
        ]
    )


def test_append_slash_redirect():
    def app(env, sr):
        return utils.append_slash_redirect(env)(env, sr)

    client = Client(app, BaseResponse)
    response = client.get("foo", base_url="http://example.org/app")
    assert response.status_code == 301
    assert response.headers["Location"] == "http://example.org/app/foo/"


def test_cached_property_doc():
    @utils.cached_property
    def foo():
        """testing"""
        return 42

    assert foo.__doc__ == "testing"
    assert foo.__name__ == "foo"
    assert foo.__module__ == __name__


def test_secure_filename():
    assert utils.secure_filename("My cool movie.mov") == "My_cool_movie.mov"
    assert utils.secure_filename("../../../etc/passwd") == "etc_passwd"
    assert (
        utils.secure_filename(u"i contain cool \xfcml\xe4uts.txt")
        == "i_contain_cool_umlauts.txt"
    )
    assert utils.secure_filename("__filename__") == "filename"
    assert utils.secure_filename("foo$&^*)bar") == "foobar"
