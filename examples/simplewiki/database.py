from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import join
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy.orm import create_session
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relation
from sqlalchemy.orm import scoped_session

from .utils import application
from .utils import parse_creole

try:
    from greenlet import getcurrent as get_ident
except ImportError:
    from threading import get_ident

# create a global metadata
metadata = MetaData()


def new_db_session():
    """
    This function creates a new session if there is no session yet for
    the current context.  It looks up the application and if it finds
    one it creates a session bound to the active database engine in that
    application.  If there is no application bound to the context it
    raises an exception.
    """
    return create_session(application.database_engine, autoflush=True, autocommit=False)


# and create a new global session factory.  Calling this object gives
# you the current active session
session = scoped_session(new_db_session, get_ident)


# our database tables.
page_table = Table(
    "pages",
    metadata,
    Column("page_id", Integer, primary_key=True),
    Column("name", String(60), unique=True),
)

revision_table = Table(
    "revisions",
    metadata,
    Column("revision_id", Integer, primary_key=True),
    Column("page_id", Integer, ForeignKey("pages.page_id")),
    Column("timestamp", DateTime),
    Column("text", String),
    Column("change_note", String(200)),
)


class Revision:
    """
    Represents one revision of a page.
    This is useful for editing particular revision of pages or creating
    new revisions.  It's also used for the diff system and the revision
    log.
    """

    query = session.query_property()

    def __init__(self, page, text, change_note="", timestamp=None):
        if isinstance(page, int):
            self.page_id = page
        else:
            self.page = page
        self.text = text
        self.change_note = change_note
        self.timestamp = timestamp or datetime.utcnow()

    def render(self):
        """Render the page text into a genshi stream."""
        return parse_creole(self.text)

    def __repr__(self):
        return f"<{type(self).__name__} {self.page_id!r}:{self.revision_id!r}>"


class Page:
    """
    Represents a simple page without any revisions.  This is for example
    used in the page index where the page contents are not relevant.
    """

    query = session.query_property()

    def __init__(self, name):
        self.name = name

    @property
    def title(self):
        return self.name.replace("_", " ")

    def __repr__(self):
        return f"<{type(self).__name__} {self.name!r}>"


class RevisionedPage(Page, Revision):
    """
    Represents a wiki page with a revision.  Thanks to multiple inheritance
    and the ability of SQLAlchemy to map to joins we can combine `Page` and
    `Revision` into one class here.
    """

    query = session.query_property()

    def __init__(self):
        raise TypeError(
            "cannot create WikiPage instances, use the Page and "
            "Revision classes for data manipulation."
        )

    def __repr__(self):
        return f"<{type(self).__name__} {self.name!r}:{self.revision_id!r}>"


# setup mappers
mapper(Revision, revision_table)
mapper(
    Page,
    page_table,
    properties=dict(
        revisions=relation(
            Revision, backref="page", order_by=Revision.revision_id.desc()
        )
    ),
)
mapper(
    RevisionedPage,
    join(page_table, revision_table),
    properties=dict(page_id=[page_table.c.page_id, revision_table.c.page_id]),
)
