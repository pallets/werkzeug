#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage plnt
    ~~~~~~~~~~~

    This script manages the plnt application.

    :copyright: (c) 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from werkzeug import script


def make_app():
    """Helper function that creates a plnt app."""
    from plnt import Plnt
    database_uri = os.environ.get('PLNT_DATABASE_URI')
    app = Plnt(database_uri or 'sqlite:////tmp/plnt.db')
    app.bind_to_context()
    return app


action_runserver = script.make_runserver(make_app, use_reloader=True)
action_shell = script.make_shell(lambda: {'app': make_app()})


def action_initdb():
    """Initialize the database"""
    from plnt.database import Blog, session
    make_app().init_database()
    # and now fill in some python blogs everybody should read (shamelessly
    # added my own blog too)
    blogs = [
        Blog('Armin Ronacher', 'http://lucumr.pocoo.org/',
             'http://lucumr.pocoo.org/cogitations/feed/'),
        Blog('Georg Brandl', 'http://pyside.blogspot.com/',
             'http://pyside.blogspot.com/feeds/posts/default'),
        Blog('Ian Bicking', 'http://blog.ianbicking.org/',
             'http://blog.ianbicking.org/feed/'),
        Blog('Amir Salihefendic', 'http://amix.dk/',
             'http://feeds.feedburner.com/amixdk'),
        Blog('Christopher Lenz', 'http://www.cmlenz.net/blog/',
             'http://www.cmlenz.net/blog/atom.xml'),
        Blog('Frederick Lundh', 'http://online.effbot.org/',
             'http://online.effbot.org/rss.xml')
    ]
    # okay. got tired here.  if someone feels that he is missing, drop me
    # a line ;-)
    for blog in blogs:
        session.add(blog)
    session.commit()
    print 'Initialized database, now run manage-plnt.py sync to get the posts'


def action_sync():
    """Sync the blogs in the planet.  Call this from a cronjob."""
    from plnt.sync import sync
    make_app().bind_to_context()
    sync()


if __name__ == '__main__':
    script.run()
