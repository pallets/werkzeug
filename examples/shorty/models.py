from datetime import datetime
from sqlalchemy import Table, Column, String, Boolean, DateTime
from sqlalchemy.orm import mapper
from shorty.utils import session, metadata, url_for, get_random_uid

url_table = Table('urls', metadata,
    Column('uid', String(140), primary_key=True),
    Column('target', String(500)),
    Column('added', DateTime),
    Column('public', Boolean)
)

class URL(object):
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
        return url_for('link', uid=self.uid, _external=True)

    def __repr__(self):
        return '<URL %r>' % self.uid

mapper(URL, url_table)
