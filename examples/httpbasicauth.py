# -*- coding: utf-8 -*-
"""
    HTTP Basic Auth Example
    ~~~~~~~~~~~~~~~~~~~~~~~

    Shows how you can implement HTTP basic auth support without an
    additional component.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
from werkzeug import Request, Response, run_simple


class Application(object):

    def __init__(self, users, realm='login required'):
        self.users = users
        self.realm = realm

    def check_auth(self, username, password):
        return username in self.users and self.users[username] == password

    def auth_required(self, request):
        return Response('Could not verify your access level for that URL.\n'
                        'You have to login with proper credentials', 401,
                        {'WWW-Authenticate': 'Basic realm="%s"' % self.realm})

    def dispatch_request(self, request):
        return Response('Logged in as %s' % request.environ['REMOTE_USER'])

    def __call__(self, environ, start_response):
        request = Request(environ)
        auth = request.authorization
        if not auth or not self.check_auth(auth.username, auth.password):
            response = self.auth_required(request)
        else:
            response = self.dispatch_request(request)
        return response(request)(environ, start_response)


if __name__ == '__main__':
    application = Application({'user1': 'password', 'user2': 'password'})
    run_simple('localhost', 5000, application)
