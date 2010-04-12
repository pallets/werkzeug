# -*- coding: utf-8 -*-
"""
    plnt.database
    ~~~~~~~~~~~~~

    The database definitions for the planet.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD.
"""
from sqlalchemy import MetaData, Table, Column, ForeignKey, Boolean, \
     Integer, String, DateTime
from sqlalchemy.orm import dynamic_loader, scoped_session, create_session, \
     mapper
from plnt.utils import application, local_manager


def new_db_session():
    return create_session(application.database_engine, autoflush=True,
                          autocommit=False)

metadata = MetaData()
session = scoped_session(new_db_session, local_manager.get_ident)


blog_table = Table('blogs', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(120)),
    Column('description', String),
    Column('url', String(200)),
    Column('feed_url', String(250))
)

entry_table = Table('entries', metadata,
    Column('id', Integer, primary_key=True),
    Column('blog_id', Integer, ForeignKey('blogs.id')),
    Column('guid', String(200), unique=True),
    Column('title', String(140)),
    Column('url', String(200)),
    Column('text', String),
    Column('pub_date', DateTime),
    Column('last_update', DateTime)
)


class Blog(object):
    query = session.query_property()

    def __init__(self, name, url, feed_url, description=u''):
        self.name = name
        self.url = url
        self.feed_url = feed_url
        self.description = description

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.url)


class Entry(object):
    query = session.query_property()

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.guid)


mapper(Entry, entry_table)
mapper(Blog, blog_table, properties=dict(
    entries=dynamic_loader(Entry, backref='blog')
))
