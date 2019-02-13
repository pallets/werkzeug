#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage SimpleWiki
    ~~~~~~~~~~~~~~~~~

    This script provides some basic commands to debug and test SimpleWiki.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import os

import click
from werkzeug.serving import run_simple


def make_wiki():
    """Helper function that creates a new wiki instance."""
    from simplewiki import SimpleWiki

    database_uri = os.environ.get("SIMPLEWIKI_DATABASE_URI")
    return SimpleWiki(database_uri or "sqlite:////tmp/simplewiki.db")


def make_shell():
    from simplewiki import database

    wiki = make_wiki()
    wiki.bind_to_context()
    return {"wiki": wiki, "db": database}


@click.group()
def cli():
    pass


@cli.command()
def initdb():
    make_wiki().init_database()


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
    app = make_wiki()
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
    namespace = make_shell()
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


if __name__ == "__main__":
    cli()
