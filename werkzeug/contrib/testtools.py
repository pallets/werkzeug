"""
    werkzeug.contrib.testtools
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    
    This Module implements a extended wrappers for simplified Testing

    `TestResponse`
        a response wrapper wich adds various cached attributes for 
        simplified assertions on various contenttypes
    
    :copyright: 2007 by Ronny Pfannschmidt.
    :license: BSD, see LICENSE for more details.
"""


from werkzeug import BaseResponse, cached_property, import_string, environ_property


class TestResponse(BaseResponse):
    """
    """

    def __init__(self, *k, **kw):
        BaseResponse.__init__(self, *k, **kw)
        self.content_type = self.headers['Content-Type']
        self.mimetype = self.content_type.split(';')[0].strip()
    
    def test_client_callback(self, client, environ):
        self.client = client
        self.environ = environ

    werkzeug_request = environ_property('werkzeug.request')

    def xml(self):
        """
        gets an etree if possible
        """
        if 'xml' not in self.mimetype:
            raise AttributeError(
                'Not a XML response (Content-Type: %s)'
                % self.mimetype)
        for module in [
                'xml.etree.ElemenTree',
                'ElementTree',
                'elementtree.ElementTree']:
            try:
                etree = import_string(module)
                break
            except ImportError:
                continue
            else:
                raise RuntimeError(
                    'You must have ElementTree installed '
                    '(or use Python 2.5) to use TestResponse.xml')
        return etree.XML(self.body)
    xml = cached_property(xml)

    def lxml(self):
        """
        gets a lxml etree if possible
        """
        if ('html' not in self.mimetype and
            'xml' not in self.mimetype):
            raise AttributeError(
                'Not a HTML/XML response (Content-Type: %s)'
                % self.mimetype)
        
        from lxml import etree
        try:
            from lxml.html import fromstring
        except ImportError:
            fromstring = etree.HTML
        if self.mimetype=='text/html':
            return fromstring(self.response_body)
        else:
            return etree.XML(self.response_body)
    lxml = cached_property(lxml)


    def json(self):
        """
        gets the result of simplejson.loads if possible
        """
        if 'json' not in self.mimetype:
            raise AttributeError(
                'Not a JSON response (Content-Type: %s)'
                % self.mimetype)
        from simplejson import loads
        return loads(self.response_body)
    json = cached_property(json)

