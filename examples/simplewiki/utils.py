# -*- coding: utf-8 -*-
"""
    simplewiki.utils
    ~~~~~~~~~~~~~~~~

    Various utilities.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: BSD.
"""
import difflib
from os import path
from genshi import Stream
from genshi.template import TemplateLoader
from creoleparser import Parser, Creole10
from werkzeug import BaseRequest, BaseResponse, Local, LocalManager, \
     url_encode, url_quote, redirect


# calculate the path to the templates an create the template loader
TEMPLATE_PATH = path.join(path.dirname(__file__), 'templates')
template_loader = TemplateLoader(TEMPLATE_PATH, auto_reload=True,
                                 variable_lookup='lenient')


# context locals
local = Local()
local_manager = LocalManager([local])


def get_request():
    """Get the current active request or None."""
    return getattr(local, 'request', None)


def get_application():
    """Get the current active application or None."""
    return getattr(local, 'application', None)


def generate_template(template_name, **context):
    """Load and generate a template."""
    request = get_request()
    if request:
        context['request'] = request
    context.update(
        href=href,
        format_datetime=format_datetime
    )
    return template_loader.load(template_name).generate(**context)


def parse_creole(request, markup):
    """Parse some creole markup and create a genshi stream."""
    return Parser(dialect=Creole10(
        wiki_links_base_url=request.url_root,
        wiki_links_space_char='_',
        no_wiki_monospace=True,
        use_additions=True
    )).generate(markup)


def href(*args, **kw):
    """Simple function for URL generation."""
    request = get_request()
    result = [(request and request.script_root or '') + '/']
    for idx, arg in enumerate(args):
        result.append((idx and '/' or '') + url_quote(arg))
    if kw:
        result.append('?' + url_encode(kw))
    return ''.join(result)


def format_datetime(obj):
    """Format a datetime object."""
    return obj.strftime('%Y-%m-%d %H:%M')


class Request(BaseRequest):
    """
    Encapsulates a request.
    """

    def __init__(self, environ, wiki):
        BaseRequest.__init__(self, environ)
        self.wiki = wiki
        local.request = self

    def from_values(app, *args, **kw):
        """Compatibility with the normal from_values."""
        return app.create_request(*args, **kw)
    from_values = staticmethod(from_values)


class Response(BaseResponse):
    """
    Encapsulates a WSGI response.  Unlike the default response object werkzeug
    provides, this accepts a genshi stream and will automatically render it
    to html.  This makes it possible to switch to xhtml or html5 easily.
    """

    default_mimetype = 'text/html'

    def __init__(self, response=None, status=200, headers=None, mimetype=None,
                 content_type=None):
        if isinstance(response, Stream):
            response = response.render('html', encoding=None, doctype='html')
        BaseResponse.__init__(self, response, status, headers, mimetype,
                              content_type)


class Pagination(object):
    """
    Paginate a SQLAlchemy query object.
    """

    def __init__(self, query, per_page, page, link):
        self.query = query
        self.per_page = per_page
        self.page = page
        self.link = link
        self._count = None

    @property
    def entries(self):
        return self.query.offset((self.page - 1) * self.per_page) \
                         .limit(self.per_page)

    @property
    def has_previous(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def previous(self):
        return href(self.link, page=self.page - 1)

    @property
    def next(self):
        return href(self.link, page=self.page + 1)

    @property
    def count(self):
        if self._count is None:
            self._count = self.query.count()
        return self._count

    @property
    def pages(self):
        return max(0, self.count - 1) // self.per_page + 1
