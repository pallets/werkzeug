from datetime import datetime
from couchdb.schema import Document, TextField, BooleanField, DateTimeField
from couchy.utils import url_for, get_random_uid


class URL(Document):
    target = TextField()
    public = BooleanField()
    added = DateTimeField(default=datetime.utcnow())
    shorty_id = TextField(default=None)
    db = None

    @classmethod
    def load(self, id):
        return super(URL, self).load(URL.db, id)

    @classmethod
    def query(self, code):
        return URL.db.query(code)

    def store(self):
        if getattr(self._data, 'id', None) is None:
            new_id = self.shorty_id if self.shorty_id else None
            while 1:
                id = new_id if new_id else get_random_uid()
                docid = None
                try:
                    docid = URL.db.resource.put(content=self._data, path='/%s/' % str(id))['id']
                except:
                    continue
                if docid:
                    break
            self._data = URL.db.get(docid)
        else:
            super(URL, self).store(URL.db)
        return self

    @property
    def short_url(self):
        return url_for('link', uid=self.id, _external=True)

    def __repr__(self):
        return '<URL %r>' % self.id
