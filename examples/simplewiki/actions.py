"""The per page actions. The actions are defined in the URL with the
``action`` parameter and directly dispatched to the functions in this
module. In the module the actions are prefixed with '`on_`', so be
careful not to name any other objects in the module with the same prefix
unless you want to act them as actions.
"""
from difflib import unified_diff

from werkzeug.utils import redirect

from .database import Page
from .database import Revision
from .database import RevisionedPage
from .database import session
from .utils import format_datetime
from .utils import generate_template
from .utils import href
from .utils import Response


def on_show(request, page_name):
    """Displays the page the user requests."""
    revision_id = request.args.get("rev", type=int)
    query = RevisionedPage.query.filter_by(name=page_name)
    if revision_id:
        query = query.filter_by(revision_id=revision_id)
        revision_requested = True
    else:
        query = query.order_by(RevisionedPage.revision_id.desc())
        revision_requested = False
    page = query.first()
    if page is None:
        return page_missing(request, page_name, revision_requested)
    return Response(generate_template("action_show.html", page=page))


def on_edit(request, page_name):
    """Edit the current revision of a page."""
    change_note = error = ""
    revision = (
        Revision.query.filter(
            (Page.name == page_name) & (Page.page_id == Revision.page_id)
        )
        .order_by(Revision.revision_id.desc())
        .first()
    )
    if revision is None:
        page = None
    else:
        page = revision.page

    if request.method == "POST":
        text = request.form.get("text")
        if request.form.get("cancel") or revision and revision.text == text:
            return redirect(href(page.name))
        elif not text:
            error = "You cannot save empty revisions."
        else:
            change_note = request.form.get("change_note", "")
            if page is None:
                page = Page(page_name)
                session.add(page)
            session.add(Revision(page, text, change_note))
            session.commit()
            return redirect(href(page.name))

    return Response(
        generate_template(
            "action_edit.html",
            revision=revision,
            page=page,
            new=page is None,
            page_name=page_name,
            change_note=change_note,
            error=error,
        )
    )


def on_log(request, page_name):
    """Show the list of recent changes."""
    page = Page.query.filter_by(name=page_name).first()
    if page is None:
        return page_missing(request, page_name, False)
    return Response(generate_template("action_log.html", page=page))


def on_diff(request, page_name):
    """Show the diff between two revisions."""
    old = request.args.get("old", type=int)
    new = request.args.get("new", type=int)
    error = ""
    diff = page = old_rev = new_rev = None

    if not (old and new):
        error = "No revisions specified."
    else:
        revisions = {
            x.revision_id: x
            for x in Revision.query.filter(
                (Revision.revision_id.in_((old, new)))
                & (Revision.page_id == Page.page_id)
                & (Page.name == page_name)
            )
        }
        if len(revisions) != 2:
            error = "At least one of the revisions requested does not exist."
        else:
            new_rev = revisions[new]
            old_rev = revisions[old]
            page = old_rev.page
            diff = unified_diff(
                f"{old_rev.text}\n".splitlines(True),
                f"{new_rev.text}\n".splitlines(True),
                page.name,
                page.name,
                format_datetime(old_rev.timestamp),
                format_datetime(new_rev.timestamp),
                3,
            )

    return Response(
        generate_template(
            "action_diff.html",
            error=error,
            old_revision=old_rev,
            new_revision=new_rev,
            page=page,
            diff=diff,
        )
    )


def on_revert(request, page_name):
    """Revert an old revision."""
    rev_id = request.args.get("rev", type=int)

    old_revision = page = None
    error = "No such revision"

    if request.method == "POST" and request.form.get("cancel"):
        return redirect(href(page_name))

    if rev_id:
        old_revision = Revision.query.filter(
            (Revision.revision_id == rev_id)
            & (Revision.page_id == Page.page_id)
            & (Page.name == page_name)
        ).first()
        if old_revision:
            new_revision = (
                Revision.query.filter(
                    (Revision.page_id == Page.page_id) & (Page.name == page_name)
                )
                .order_by(Revision.revision_id.desc())
                .first()
            )
            if old_revision == new_revision:
                error = "You tried to revert the current active revision."
            elif old_revision.text == new_revision.text:
                error = (
                    "There are no changes between the current "
                    "revision and the revision you want to "
                    "restore."
                )
            else:
                error = ""
                page = old_revision.page
                if request.method == "POST":
                    change_note = request.form.get("change_note", "")

                    if change_note:
                        change_note = f"revert: {change_note}"
                    else:
                        change_note = "revert"

                    session.add(Revision(page, old_revision.text, change_note))
                    session.commit()
                    return redirect(href(page_name))

    return Response(
        generate_template(
            "action_revert.html", error=error, old_revision=old_revision, page=page
        )
    )


def page_missing(request, page_name, revision_requested, protected=False):
    """Displayed if page or revision does not exist."""
    return Response(
        generate_template(
            "page_missing.html",
            page_name=page_name,
            revision_requested=revision_requested,
            protected=protected,
        ),
        status=404,
    )


def missing_action(request, action):
    """Displayed if a user tried to access a action that does not exist."""
    return Response(generate_template("missing_action.html", action=action), status=404)
