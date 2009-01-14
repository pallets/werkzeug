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
    """TestTools json descriptor"""
    resp = response('{ "a": 1}', 'application/json')
    assert resp.json == {'a': 1}

def test_json_fail():
    """TestTools json descriptor fail"""
    resp = response('{ "a": 1}', 'text/plain')
    assert_raises(AttributeError, lambda: resp.json)

def test_lxml_html():
    """TestTools lxml HTML descriptor"""
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'text/html')
    assert resp.lxml.xpath('//text()') == ['Test']

def test_lxml_xml():
    """TestTools lxml XML descriptor"""
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'application/xml')
    assert resp.lxml.xpath('//text()') == ['Test']

def test_lxml_fail():
    """TestTools lxml descriptor fail"""
    resp = response(
            '<html><head><title>Test</title></head></html>',
            'text/plain')
    assert_raises(AttributeError, lambda: resp.lxml)
