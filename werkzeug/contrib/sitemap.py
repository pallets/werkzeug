# -*- coding: utf-8 -*-
"""
    werkzeug.contrib.sitemap
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides a class called :class:`Sitemap` which can be used to
    generate sitemap.xml in the sitemap XML format. For more information
    please refer to http://sitemaps.org/protocol.html.

    Example::

        def sitemap():
            xml = Sitemap()

            for post in Post.query.limit(10).all():
                xml.add_url(post.url, lastmod=post.last_update,
                        changefreq='weekly', priority=0.8)

            return xml.get_response()
"""
from datetime import datetime
from werkzeug.utils import escape
from werkzeug.wrappers import BaseResponse

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def format_iso8601(obj):
    """Format a datetime object for iso8601"""
    return obj.strftime('%Y-%m-%dT%H:%M:%SZ')


class Sitemap(object):
    """A helper class that creates sitemap.xml."""

    def __init__(self, urls=None):
        self.urls = urls and list(urls) or []

    def add_url(self, *args, **kwargs):
        """Add a new url to the sitemap. This function can either be called
        with a :class:`UrlEntry` or some keyword and positional arguments that
        are forwarded to the :class:`UrlEntry` constructor.
        """
        if len(args) == 1 and not kwargs and isinstance(args[0], UrlEntry):
            self.urls.append(args[0])
        else:
            self.urls.append(UrlEntry(*args, **kwargs))

    def __repr__(self):
        return '<%s (%d entrie(s))>' % (
            self.__class__.__name__,
            len(self.urls)
        )

    def generate(self):
        """Return a generate that yeilds pieces of XML."""
        yield u'<?xml version="1.0" encoding="utf-8"?>\n'
        yield u'<urlset xmlns="%s">\n' % SITEMAP_NS
        for url in self.urls:
            for line in url.generate():
                yield u'  ' + line
        yield u'</urlset>\n'

    def to_string(self):
        """Convert the sitemap into a string."""
        return u''.join(self.generate())

    def get_response(self):
        return BaseResponse(self.to_string(), mimetype='text/xml')

    def __call__(self, environ, start_response):
        """Use the class as WSGI response object."""
        return self.get_response()(environ, start_response)

    def __unicode__(self):
        return self.to_string()

    def __str__(self):
        return self.to_string().encode('utf-8')


class UrlEntry(object):
    """Represents a single url entry in the sitemap.

    :param loc: the localtion of the url. Required.
    :param lastmod: the time the url was modified the last time. Must be a
    :class:`datetime.datetime` object or a string representing the time in
    ISO format, %Y-%m-%d.
    :param changefreq: how frequently the content of the url is likely to
    change. One of ``'always'``, ``'hourly'``, ``'daily'``, ``'weekly'``,
    ``'monthly'``, ``'yearly'``, ``'never'``.
    :param priority: the priority of this url relative to the other urls on
    your site. Valid values from 0.0 to 1.0.
    """

    freq_values = [
            'always', 'hourly', 'daily', 'weekly',
            'monthly', 'yearly', 'never'
    ]

    def __init__(self, loc=None, **kwargs):
        self.loc = loc
        self.lastmod = kwargs.get('lastmod')
        self.changefreq = kwargs.get('changefreq')
        self.priority = kwargs.get('priority')

        if self.loc is None:
            raise ValueError('location is required')

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.loc
        )

    def generate(self):
        """Yields pieces of XML."""
        yield u'<url>\n'
        yield u'<loc>%s</loc>\n' % escape(self.loc, True)
        if self.lastmod and not isinstance(self.lastmod, str):
            self.lastmod = self.lastmod.strftime('%Y-%m-%d')
            yield u'<lastmod>%s</lastmod>\n' % self.lastmod
        if self.changefreq and self.changefreq in self.freq_values:
            yield u'<changefreq>%s</changefreq>\n' % self.changefreq
        if self.priority and 0.0 <= self.priority <= 1.0:
            yield u'<priority>%s</priority>\n' % self.priority
        yield u'</url>\n'

    def to_string(self):
        """Convert the url item into a unicode object."""
        return u''.join(self.generate())

    def __unicode__(self):
        return self.to_string()

    def __str__(self):
        return self.to_string().encode('utf-8')
