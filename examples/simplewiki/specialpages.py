# -*- coding: utf-8 -*-
"""
    simplewiki.specialpages
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module contains special pages such as the recent changes page.


    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
from .actions import page_missing
from .database import Page
from .database import RevisionedPage
from .utils import generate_template
from .utils import Pagination
from .utils import Response


def page_index(request):
    """Index of all pages."""
    letters = {}
    for page in Page.query.order_by(Page.name):
        letters.setdefault(page.name.capitalize()[0], []).append(page)
    return Response(
        generate_template("page_index.html", letters=sorted(letters.items()))
    )


def recent_changes(request):
    """Display the recent changes."""
    page = max(1, request.args.get("page", type=int))
    query = RevisionedPage.query.order_by(RevisionedPage.revision_id.desc())
    return Response(
        generate_template(
            "recent_changes.html",
            pagination=Pagination(query, 20, page, "Special:Recent_Changes"),
        )
    )


def page_not_found(request, page_name):
    """
    Displays an error message if a user tried to access
    a not existing special page.
    """
    return page_missing(request, page_name, True)


pages = {"Index": page_index, "Recent_Changes": recent_changes}
