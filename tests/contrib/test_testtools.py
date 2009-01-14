from nose.tools import assert_raises

from werkzeug.contrib.testtools import *
from werkzeug import Client, BaseRequest, responder


def response(content, mimetype):
    return TestResponse(
        status=200,
        response=content,
        mimetype=mimetype,
    )

@responder
def application(environ, start_response):
    request = BaseRequest(environ)
    return response('This is a Test.', 'text/plain')

def test_json():
    resp = response('{ "a": 1}', 'application/json')
    assert resp.json == {'a': 1}

def test_json_fail():
    resp = response('{ "a": 1}', 'text/plain')
    assert_raises(AttributeError, lambda: resp.json)

def test_lxml_html():
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'text/html')
    assert resp.lxml.xpath('//text()') == ['Test']

def test_lxml_xml():
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'application/xml')
    assert resp.lxml.xpath('//text()') == ['Test']

def test_lxml_fail():
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'text/plain')
    assert_raises(AttributeError, lambda: resp.lxml)
