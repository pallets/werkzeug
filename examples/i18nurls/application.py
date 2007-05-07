from os import path
from werkzeug.wrappers import BaseRequest, BaseResponse
from werkzeug.routing import NotFound, RequestRedirect
from werkzeug.minitmpl import Template
from i18nurls.urls import map

TEMPLATES = path.join(path.dirname(__file__), 'templates')

views = {}

def expose(name):
    """Register the function as view."""
    def wrapped(f):
        views[name] = f
        return f
    return wrapped


class Request(BaseRequest):
    charset = 'utf-8'

    def __init__(self, environ, urls):
        super(Request, self).__init__(environ)
        self.urls = urls
        self.matched_url = None

    def url_for(self, endpoint, **args):
        if not 'lang_code' in args:
            args['lang_code'] = self.language
        if endpoint == 'this':
            endpoint = self.matched_url[0]
            tmp = self.matched_url[1].copy()
            tmp.update(args)
            args = tmp
        return self.urls.build(endpoint, args)


class Response(BaseResponse):
    charset = 'utf-8'


class TemplateResponse(Response):

    def __init__(self, template_name, **values):
        self.template_name = template_name
        self.template_values = values
        super(TemplateResponse, self).__init__(mimetype='text/html')

    def __call__(self, environ, start_response):
        req = environ['werkzeug.request']
        values = self.template_values.copy()
        values['req'] = req
        values['body'] = self.render_template(self.template_name, values)
        self.write(self.render_template('layout.html', values))
        return super(TemplateResponse, self).__call__(environ, start_response)

    def render_template(self, name, values):
        f = file(path.join(TEMPLATES, name))
        try:
            tmpl = Template(f.read().decode('utf-8'))
        finally:
            f.close()
        return tmpl.render(values)


class Application(object):

    def __init__(self):
        from i18nurls import views
        self.not_found = views.page_not_found

    def get_language(self, environ):
        return environ.get('HTTP_ACCEPT_LANGUAGE', 'en') \
                      .split(',')[0] \
                      .split(';')[0] \
                      .split('-')[0].lower()

    def __call__(self, environ, start_response):
        urls = map.bind_to_environ(environ)
        req = Request(environ, urls)
        try:
            endpoint, args = urls.match(req.path)
        except NotFound:
            resp = self.not_found(req)
        except RequestRedirect, e:
            resp = Response('Moved to %s' % e.new_url, status=302)
            resp.headers['Location'] = e.new_url
        else:
            req.matched_url = (endpoint, args)
            if endpoint == '#language_select':
                lng = self.get_language(environ)
                index_url = urls.build('index', {'lang_code': lng})
                resp = Response('Moved to %s' % index_url, status=302)
                resp.headers['Location'] = index_url
            else:
                req.language = args.pop('lang_code', None)
                resp = views[endpoint](req, **args)
        return resp(environ, start_response)
