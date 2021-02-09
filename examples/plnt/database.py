from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy.orm import create_session
from sqlalchemy.orm import dynamic_loader
from sqlalchemy.orm import mapper
from sqlalchemy.orm import scoped_session

from .utils import application

try:
    from greenlet import getcurrent as get_ident
except ImportError:
    from threading import get_ident


def new_db_session():
    return create_session(application.database_engine, autoflush=True, autocommit=False)


metadata = MetaData()
session = scoped_session(new_db_session, get_ident)


blog_table = Table(
    "blogs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(120)),
    Column("description", String),
    Column("url", String(200)),
    Column("feed_url", String(250)),
)

entry_table = Table(
    "entries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("blog_id", Integer, ForeignKey("blogs.id")),
    Column("guid", String(200), unique=True),
    Column("title", String(140)),
    Column("url", String(200)),
    Column("text", String),
    Column("pub_date", DateTime),
    Column("last_update", DateTime),
)


class Blog:
    query = session.query_property()

    def __init__(self, name, url, feed_url, description=""):
        self.name = name
        self.url = url
        self.feed_url = feed_url
        self.description = description

    def __repr__(self):
        return f"<{type(self).__name__} {self.url!r}>"


class Entry:
    query = session.query_property()

    def __repr__(self):
        return f"<{type(self).__name__} {self.guid!r}>"


mapper(Entry, entry_table)
mapper(Blog, blog_table, properties=dict(entries=dynamic_loader(Entry, backref="blog")))
