# -*- coding: utf-8 -*-
"""
    simplewiki.utils
    ~~~~~~~~~~~~~~~~

    This module implements various utility functions and classes used all
    over the application.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from os import path

import creoleparser
from genshi import Stream
from genshi.template import TemplateLoader
from werkzeug.local import Local
from werkzeug.local import LocalManager
from werkzeug.urls import url_encode
from werkzeug.urls import url_quote
from werkzeug.utils import cached_property
from werkzeug.wrappers import BaseRequest
from werkzeug.wrappers import BaseResponse


# calculate the path to the templates an create the template loader
TEMPLATE_PATH = path.join(path.dirname(__file__), "templates")
template_loader = TemplateLoader(
    TEMPLATE_PATH, auto_reload=True, variable_lookup="lenient"
)


# context locals.  these two objects are use by the application to
# bind objects to the current context.  A context is defined as the
# current thread and the current greenlet if there is greenlet support.
local = Local()
local_manager = LocalManager([local])
request = local("request")
application = local("application")

# create a new creole parser
creole_parser = creoleparser.Parser(
    dialect=creoleparser.create_dialect(
        creoleparser.creole10_base,
        wiki_links_base_url="",
        wiki_links_path_func=lambda page_name: href(page_name),
        wiki_links_space_char="_",
        no_wiki_monospace=True,
    ),
    method="html",
)


def generate_template(template_name, **context):
    """Load and generate a template."""
    context.update(href=href, format_datetime=format_datetime)
    return template_loader.load(template_name).generate(**context)


def parse_creole(markup):
    """Parse some creole markup and create a genshi stream."""
    return creole_parser.generate(markup)


def href(*args, **kw):
    """
    Simple function for URL generation.  Position arguments are used for the
    URL path and keyword arguments are used for the url parameters.
    """
    result = [(request.script_root if request else "") + "/"]
    for idx, arg in enumerate(args):
        result.append(("/" if idx else "") + url_quote(arg))
    if kw:
        result.append("?" + url_encode(kw))
    return "".join(result)


def format_datetime(obj):
    """Format a datetime object."""
    return obj.strftime("%Y-%m-%d %H:%M")


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

    default_mimetype = "text/html"

    def __init__(
        self, response=None, status=200, headers=None, mimetype=None, content_type=None
    ):
        if isinstance(response, Stream):
            response = response.render("html", encoding=None, doctype="html")
        BaseResponse.__init__(self, response, status, headers, mimetype, content_type)


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

    @cached_property
    def entries(self):
        return (
            self.query.offset((self.page - 1) * self.per_page)
            .limit(self.per_page)
            .all()
        )

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

    @cached_property
    def count(self):
        return self.query.count()

    @property
    def pages(self):
        return max(0, self.count - 1) // self.per_page + 1
