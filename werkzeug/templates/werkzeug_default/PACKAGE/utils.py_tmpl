# -*- coding: <%= FILE_ENCODING %> -*-
<%= make_docstring(MODULE, '''\
This module contains the subclasses of the base request and response
objects provided by werkzeug. The subclasses know about their charset
and implement some additional functionallity like the ability to link
to view functions.''') %>
from werkzeug.wrappers import BaseRequest, BaseResponse


class Request(BaseRequest):
    charset = '<%= FILE_ENCODING %>'

    def __init__(self, environ, url_adapter):
        super(Request, self).__init__(environ)
        self.url_adapter = url_adapter

    def url_for(self, endpoint, **values):
        return self.url_adapter.build(endpoint, values)

    def external_url_for(self, endpoint, **values):
        return self.url_adapter.build(endpoint, values, True)


class Response(BaseResponse):
    charset = '<%= FILE_ENCODING %>'


class RedirectResponse(Response):

    def __init__(self, url, code=302):
        super(RedirectResponse, self).__init__('page moved to %s' % url)
        self.status = code
        self.headers['Location'] = url
