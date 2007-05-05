#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Minimal WSGI Application using werkzeug
"""
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect
from werkzeug.minitmpl import Template
from werkzeug.wrappers import BaseRequest, BaseResponse


TEMPLATES = {
    'not_found': '<h1>Page Not Found</h1>',
    'index': '<h1>Index</h1>',
    'downloads': '<h1>Downloads</h1>',
    'download_detail': '<h1>Download <?= download_id ?></h1>'
}


class Request(BaseRequest):
    charset = 'utf-8'

class Response(BaseResponse):
    charset = 'utf-8'


class TemplateResponse(Response):

    def __init__(self, template_name, **context):
        tmpl = Template(TEMPLATES[template_name])
        super(TemplateResponse, self).__init__(tmpl.render(context),
                                               mimetype='text/html; '
                                                        'charset=utf-8')


class MiniApplication(object):

    def __init__(self, server_name, script_name):
        self.script_name = script_name
        self.map = Map([
            Rule('/', endpoint='index'),
            Rule('/downloads/', endpoint='downloads_index'),
            Rule('/downloads/<int:download_id>', endpoint='downloads_show')
        ], server_name, '')

    def on_page_not_found(self, req):
        return TemplateResponse('not_found')

    def on_index(self, req):
        return TemplateResponse('index')

    def on_downloads_index(self, req):
        return TemplateResponse('downloads')

    def on_downloads_show(self, req, download_id):
        return TemplateResponse('download_detail', download_id=download_id)

    def __call__(self, environ, start_response):
        req = Request(environ)
        try:
            endpoint, arguments = self.map.match(req.path, self.script_name)
        except NotFound, e:
            endpoint = 'page_not_found'
            arguments = {}
        except RequestRedirect, e:
            print e.new_url
            start_response('302 MOVED', [('Location', e.new_url)])
            return ['moved to %r' % e.new_url]
        handler = getattr(self, 'on_' + endpoint)
        return handler(req, **arguments)(environ, start_response)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    from werkzeug.debug import DebuggedApplication
    application = MiniApplication('localhost:4000', '/')
    application = DebuggedApplication(application)
    srv = make_server('localhost', 4000, application)
    srv.serve_forever()
