#!/usr/bin/env python
# -*- coding: utf-8 -*-
from werkzeug.serving import run_simple
from werkzeug.contrib.sessions import SessionStore, SessionMiddleware


class MemorySessionStore(SessionStore):

    def __init__(self, session_class=None):
        SessionStore.__init__(self, session_class=None)
        self.sessions = {}

    def save(self, session):
        self.sessions[session.sid] = session

    def delete(self, session):
        self.sessions.pop(session.id, None)

    def get(self, sid):
        if not self.is_valid_key(sid) or sid not in self.sessions:
            return self.new()
        return self.session_class(self.sessions[sid], sid, False)


def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/html')])
    session = environ['werkzeug.session']
    yield '<title>Session Example</title><h1>Session Example</h1>'
    if session.new:
        session['visit_count'] = 0
        yield '<p>This is a new session.</p>'
    session['visit_count'] += 1
    yield '<p>You visited this page %d times.</p>' % session['visit_count']


def make_app():
    return SessionMiddleware(application, MemorySessionStore())


if __name__ == '__main__':
    run_simple('localhost', 5000, make_app())
