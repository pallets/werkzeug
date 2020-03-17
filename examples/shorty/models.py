from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy.orm import mapper

from .utils import get_random_uid
from .utils import metadata
from .utils import session
from .utils import url_for

url_table = Table(
    "urls",
    metadata,
    Column("uid", String(140), primary_key=True),
    Column("target", String(500)),
    Column("added", DateTime),
    Column("public", Boolean),
)


class URL:
    query = session.query_property()

    def __init__(self, target, public=True, uid=None, added=None):
        self.target = target
        self.public = public
        self.added = added or datetime.utcnow()
        if not uid:
            while 1:
                uid = get_random_uid()
                if not URL.query.get(uid):
                    break
        self.uid = uid
        session.add(self)

    @property
    def short_url(self):
        return url_for("link", uid=self.uid, _external=True)

    def __repr__(self):
        return f"<URL {self.uid!r}>"


mapper(URL, url_table)
