from os import path
from urlparse import urlparse
from random import sample, randrange
from jinja import Environment, FileSystemLoader
from werkzeug.local import Local, LocalManager
from werkzeug.utils import cached_property
from werkzeug.wrappers import Response
from werkzeug.routing import Map, Rule

TEMPLATE_PATH = path.join(path.dirname(__file__), 'templates')
STATIC_PATH = path.join(path.dirname(__file__), 'static')
ALLOWED_SCHEMES = frozenset(['http', 'https', 'ftp', 'ftps'])
URL_CHARS = 'abcdefghijkmpqrstuvwxyzABCDEFGHIJKLMNPQRST23456789'

local = Local()
local_manager = LocalManager([local])
application = local('application')

url_map = Map([Rule('/static/<file>', endpoint='static', build_only=True)])

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))


def expose(rule, **kw):
    def decorate(f):
        kw['endpoint'] = f.__name__
        url_map.add(Rule(rule, **kw))
        return f
    return decorate

def url_for(endpoint, _external=False, **values):
    return local.url_adapter.build(endpoint, values, force_external=_external)
jinja_env.globals['url_for'] = url_for

def render_template(template, **context):
    return Response(jinja_env.get_template(template).render(**context),
                    mimetype='text/html')

def validate_url(url):
    return urlparse(url)[0] in ALLOWED_SCHEMES

def get_random_uid():
    return ''.join(sample(URL_CHARS, randrange(3, 9)))

class Pagination(object):

    def __init__(self, results, per_page, page, endpoint):
        self.results = results
        self.per_page = per_page
        self.page = page
        self.endpoint = endpoint

    @cached_property
    def count(self):
        return len(self.results)

    @cached_property
    def entries(self):
        return self.results[((self.page - 1) * self.per_page):(((self.page - 1) * self.per_page)+self.per_page)]

    has_previous = property(lambda x: x.page > 1)
    has_next = property(lambda x: x.page < x.pages)
    previous = property(lambda x: url_for(x.endpoint, page=x.page - 1))
    next = property(lambda x: url_for(x.endpoint, page=x.page + 1))
    pages = property(lambda x: max(0, x.count - 1) // x.per_page + 1)
