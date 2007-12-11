# -*- coding: utf-8 -*-
"""
    simplewiki.utils
    ~~~~~~~~~~~~~~~~

    This module implements various utility functions and classes used all
    over the application.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: BSD.
"""
import difflib
from os import path
from genshi import Stream
from genshi.template import TemplateLoader
from creoleparser import Parser, Creole10, element_store as creole_element_store
from werkzeug import BaseRequest, BaseResponse, Local, LocalManager, \
     url_encode, url_quote, redirect, lazy_property


# calculate the path to the templates an create the template loader
TEMPLATE_PATH = path.join(path.dirname(__file__), 'templates')
template_loader = TemplateLoader(TEMPLATE_PATH, auto_reload=True,
                                 variable_lookup='lenient')


# context locals.  these two objects are use by the application to
# bind objects to the current context.  A context is defined as the
# current thread and the current greenlet if there is greenlet support.
# the `get_request` and `get_application` functions look up the request
# and application objects from this local manager.
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
    # XXX: ugly hack, generate() doesn't set that thread local properly,
    # just __call__ does, which calls render() which we are not intersted
    # in ...  adapt if creole changes or mail author
    creole_element_store.d = {}
    return Parser(dialect=Creole10(
        wiki_links_base_url=request.url_root,
        wiki_links_space_char='_',
        no_wiki_monospace=True,
        use_additions=True
    )).generate(markup)


def href(*args, **kw):
    """
    Simple function for URL generation.  Position arguments are used for the
    URL path and keyword arguments are used for the url parameters.
    """
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
    Simple request subclass that allows to bind the object to the
    current context.
    """

    def bind_to_context(self):
        local.request = self


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

    @lazy_property
    def entries(self):
        return self.query.offset((self.page - 1) * self.per_page) \
                         .limit(self.per_page).all()

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

    @lazy_property
    def count(self):
        return self.query.count()

    @property
    def pages(self):
        return max(0, self.count - 1) // self.per_page + 1
