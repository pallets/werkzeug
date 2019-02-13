import hypothesis
from hypothesis.strategies import dictionaries
from hypothesis.strategies import integers
from hypothesis.strategies import lists
from hypothesis.strategies import text

from werkzeug import urls
from werkzeug.datastructures import OrderedMultiDict


@hypothesis.given(text())
def test_quote_unquote_text(t):
    assert t == urls.url_unquote(urls.url_quote(t))


@hypothesis.given(dictionaries(text(), text()))
def test_url_encoding_dict_str_str(d):
    assert OrderedMultiDict(d) == urls.url_decode(urls.url_encode(d))


@hypothesis.given(dictionaries(text(), lists(elements=text())))
def test_url_encoding_dict_str_list(d):
    assert OrderedMultiDict(d) == urls.url_decode(urls.url_encode(d))


@hypothesis.given(dictionaries(text(), integers()))
def test_url_encoding_dict_str_int(d):
    assert OrderedMultiDict({k: str(v) for k, v in d.items()}) == urls.url_decode(
        urls.url_encode(d)
    )


@hypothesis.given(text(), text())
def test_multidict_encode_decode_text(t1, t2):
    d = OrderedMultiDict()
    d.add(t1, t2)
    assert d == urls.url_decode(urls.url_encode(d))
