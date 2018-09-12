from os import path
from werkzeug.templates import Template
from werkzeug.wrappers import BaseRequest, BaseResponse
from werkzeug.routing import NotFound, RequestRedirect
from werkzeug.exceptions import HTTPException, NotFound
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
    pass


class TemplateResponse(Response):

    def __init__(self, template_name, **values):
        self.template_name = template_name
        self.template_values = values
        Response.__init__(self, mimetype='text/html')

    def __call__(self, environ, start_response):
        req = environ['werkzeug.request']
        values = self.template_values.copy()
        values['req'] = req
        values['body'] = self.render_template(self.template_name, values)
        self.write(self.render_template('layout.html', values))
        return Response.__call__(self, environ, start_response)

    def render_template(self, name, values):
        return Template.from_file(path.join(TEMPLATES, name)).render(values)


class Application(object):

    def __init__(self):
        from i18nurls import views
        self.not_found = views.page_not_found

    def __call__(self, environ, start_response):
        urls = map.bind_to_environ(environ)
        req = Request(environ, urls)
        try:
            endpoint, args = urls.match(req.path)
            req.matched_url = (endpoint, args)
            if endpoint == '#language_select':
                lng = req.accept_languages.best
                lng = lng and lng.split('-')[0].lower() or 'en'
                index_url = urls.build('index', {'lang_code': lng})
                resp = Response('Moved to %s' % index_url, status=302)
                resp.headers['Location'] = index_url
            else:
                req.language = args.pop('lang_code', None)
                resp = views[endpoint](req, **args)
        except NotFound:
            resp = self.not_found(req)
        except (RequestRedirect, HTTPException), e:
            resp = e
        return resp(environ, start_response)
