#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Cookie Based Auth
    ~~~~~~~~~~~~~~~~~

    This is a very simple application that uses a secure cookie to do the
    user authentification.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from werkzeug.contrib.securecookie import SecureCookie
from werkzeug.serving import run_simple
from werkzeug.utils import cached_property
from werkzeug.utils import escape
from werkzeug.utils import redirect
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


# don't use this key but a different one; you could just use
# os.unrandom(20) to get something random.  Changing this key
# invalidates all sessions at once.
SECRET_KEY = "\xfa\xdd\xb8z\xae\xe0}4\x8b\xea"

# the cookie name for the session
COOKIE_NAME = "session"

# the users that may access
USERS = {"admin": "default", "user1": "default"}


class AppRequest(Request):
    """A request with a secure cookie session."""

    def logout(self):
        """Log the user out."""
        self.session.pop("username", None)

    def login(self, username):
        """Log the user in."""
        self.session["username"] = username

    @property
    def logged_in(self):
        """Is the user logged in?"""
        return self.user is not None

    @property
    def user(self):
        """The user that is logged in."""
        return self.session.get("username")

    @cached_property
    def session(self):
        data = self.cookies.get(COOKIE_NAME)
        if not data:
            return SecureCookie(secret_key=SECRET_KEY)
        return SecureCookie.unserialize(data, SECRET_KEY)


def login_form(request):
    error = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if password and USERS.get(username) == password:
            request.login(username)
            return redirect("")
        error = "<p>Invalid credentials"
    return Response(
        """<title>Login</title><h1>Login</h1>
        <p>Not logged in.
        %s
        <form action="" method="post">
          <p>
            <input type="hidden" name="do" action="login">
            <input type="text" name="username" size=20>
            <input type="password" name="password", size=20>
            <input type="submit" value="Login">
        </form>"""
        % error,
        mimetype="text/html",
    )


def index(request):
    return Response(
        """<title>Logged in</title>
        <h1>Logged in</h1>
        <p>Logged in as %s
        <p><a href="/?do=logout">Logout</a>"""
        % escape(request.user),
        mimetype="text/html",
    )


@AppRequest.application
def application(request):
    if request.args.get("do") == "logout":
        request.logout()
        response = redirect(".")
    elif request.logged_in:
        response = index(request)
    else:
        response = login_form(request)
    request.session.save_cookie(response)
    return response


if __name__ == "__main__":
    run_simple("localhost", 4000, application)
