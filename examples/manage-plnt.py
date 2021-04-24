import os

import click
from werkzeug.serving import run_simple


def make_app():
    """Helper function that creates a plnt app."""
    from plnt import Plnt

    database_uri = os.environ.get("PLNT_DATABASE_URI")
    app = Plnt(database_uri or "sqlite:////tmp/plnt.db")
    app.bind_to_context()
    return app


@click.group()
def cli():
    pass


@cli.command()
def initdb():
    """Initialize the database"""
    from plnt.database import Blog, session

    make_app().init_database()
    # and now fill in some python blogs everybody should read (shamelessly
    # added my own blog too)
    blogs = [
        Blog(
            "Armin Ronacher",
            "https://lucumr.pocoo.org/",
            "https://lucumr.pocoo.org/feed.atom",
        ),
        Blog(
            "Georg Brandl",
            "https://pyside.blogspot.com/",
            "https://pyside.blogspot.com/feeds/posts/default",
        ),
        Blog(
            "Ian Bicking",
            "https://blog.ianbicking.org/",
            "https://blog.ianbicking.org/feed/",
        ),
        Blog(
            "Amir Salihefendic",
            "http://amix.dk/",
            "https://feeds.feedburner.com/amixdk",
        ),
        Blog(
            "Christopher Lenz",
            "https://www.cmlenz.net/blog/",
            "https://www.cmlenz.net/blog/atom.xml",
        ),
        Blog(
            "Frederick Lundh",
            "https://effbot.org/",
            "https://effbot.org/rss.xml",
        ),
    ]
    # okay. got tired here.  if someone feels that he is missing, drop me
    # a line ;-)
    for blog in blogs:
        session.add(blog)
    session.commit()
    click.echo("Initialized database, now run manage-plnt.py sync to get the posts")


@cli.command()
@click.option("-h", "--hostname", type=str, default="localhost", help="localhost")
@click.option("-p", "--port", type=int, default=5000, help="5000")
@click.option("--no-reloader", is_flag=True, default=False)
@click.option("--debugger", is_flag=True)
@click.option("--no-evalex", is_flag=True, default=False)
@click.option("--threaded", is_flag=True)
@click.option("--processes", type=int, default=1, help="1")
def runserver(hostname, port, no_reloader, debugger, no_evalex, threaded, processes):
    """Start a new development server."""
    app = make_app()
    reloader = not no_reloader
    evalex = not no_evalex
    run_simple(
        hostname,
        port,
        app,
        use_reloader=reloader,
        use_debugger=debugger,
        use_evalex=evalex,
        threaded=threaded,
        processes=processes,
    )


@cli.command()
@click.option("--no-ipython", is_flag=True, default=False)
def shell(no_ipython):
    """Start a new interactive python session."""
    banner = "Interactive Werkzeug Shell"
    namespace = {"app": make_app()}
    if not no_ipython:
        try:
            try:
                from IPython.frontend.terminal.embed import InteractiveShellEmbed

                sh = InteractiveShellEmbed.instance(banner1=banner)
            except ImportError:
                from IPython.Shell import IPShellEmbed

                sh = IPShellEmbed(banner=banner)
        except ImportError:
            pass
        else:
            sh(local_ns=namespace)
            return
    from code import interact

    interact(banner, local=namespace)


@cli.command()
def sync():
    """Sync the blogs in the planet.  Call this from a cronjob."""
    from plnt.sync import sync

    make_app().bind_to_context()
    sync()


if __name__ == "__main__":
    cli()
