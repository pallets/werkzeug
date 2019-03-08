# -*- coding: utf-8 -*-
"""
    plnt.sync
    ~~~~~~~~~

    Does the synchronization.  Called by "manage-plnt.py sync"

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from datetime import datetime

import feedparser
from werkzeug.utils import escape

from .database import Blog
from .database import Entry
from .database import session
from .utils import nl2p
from .utils import strip_tags


HTML_MIMETYPES = {"text/html", "application/xhtml+xml"}


def sync():
    """
    Performs a synchronization. Articles that are already syncronized aren't
    touched anymore.
    """
    for blog in Blog.query.all():
        # parse the feed. feedparser.parse will never given an exception
        # but the bozo bit might be defined.
        feed = feedparser.parse(blog.feed_url)

        for entry in feed.entries:
            # get the guid. either the id if specified, otherwise the link.
            # if none is available we skip the entry.
            guid = entry.get("id") or entry.get("link")
            if not guid:
                continue

            # get an old entry for the guid to check if we need to update
            # or recreate the item
            old_entry = Entry.query.filter_by(guid=guid).first()

            # get title, url and text. skip if no title or no text is
            # given. if the link is missing we use the blog link.
            if "title_detail" in entry:
                title = entry.title_detail.get("value") or ""
                if entry.title_detail.get("type") in HTML_MIMETYPES:
                    title = strip_tags(title)
                else:
                    title = escape(title)
            else:
                title = entry.get("title")
            url = entry.get("link") or blog.blog_url
            text = (
                "content" in entry and entry.content[0] or entry.get("summary_detail")
            )

            if not title or not text:
                continue

            # if we have an html text we use that, otherwise we HTML
            # escape the text and use that one. We also handle XHTML
            # with our tag soup parser for the moment.
            if text.get("type") not in HTML_MIMETYPES:
                text = escape(nl2p(text.get("value") or ""))
            else:
                text = text.get("value") or ""

            # no text? continue
            if not text.strip():
                continue

            # get the pub date and updated date. This is rather complex
            # because different feeds do different stuff
            pub_date = (
                entry.get("published_parsed")
                or entry.get("created_parsed")
                or entry.get("date_parsed")
            )
            updated = entry.get("updated_parsed") or pub_date
            pub_date = pub_date or updated

            # if we don't have a pub_date we skip.
            if not pub_date:
                continue

            # convert the time tuples to datetime objects.
            pub_date = datetime(*pub_date[:6])
            updated = datetime(*updated[:6])
            if old_entry and updated <= old_entry.last_update:
                continue

            # create a new entry object based on the data collected or
            # update the old one.
            entry = old_entry or Entry()
            entry.blog = blog
            entry.guid = guid
            entry.title = title
            entry.url = url
            entry.text = text
            entry.pub_date = pub_date
            entry.last_update = updated
            session.add(entry)

    session.commit()
