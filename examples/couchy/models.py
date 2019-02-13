from datetime import datetime

from couchdb.mapping import BooleanField
from couchdb.mapping import DateTimeField
from couchdb.mapping import Document
from couchdb.mapping import TextField

from .utils import get_random_uid
from .utils import url_for


class URL(Document):
    target = TextField()
    public = BooleanField()
    added = DateTimeField(default=datetime.utcnow())
    shorty_id = TextField(default=None)
    db = None

    @classmethod
    def load(cls, id):
        return super(URL, cls).load(URL.db, id)

    @classmethod
    def query(cls, code):
        return URL.db.query(code)

    def store(self):
        if getattr(self._data, "id", None) is None:
            new_id = self.shorty_id if self.shorty_id else None
            while 1:
                id = new_id if new_id else get_random_uid()
                try:
                    docid = URL.db.resource.put(
                        content=self._data, path="/%s/" % str(id)
                    )["id"]
                except Exception:
                    continue
                if docid:
                    break
            self._data = URL.db.get(docid)
        else:
            super(URL, self).store(URL.db)
        return self

    @property
    def short_url(self):
        return url_for("link", uid=self.id, _external=True)

    def __repr__(self):
        return "<URL %r>" % self.id
