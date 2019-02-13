#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Manage web.py like application
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A small example application that is built after the web.py tutorial.  We
    even use regular expression based dispatching.  The original code can be
    found on the `webpy.org webpage`__ in the tutorial section.

    __ http://webpy.org/tutorial2.en

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import os
import sys

import click
from werkzeug.serving import run_simple

from webpylike.example import app

sys.path.append(os.path.join(os.path.dirname(__file__), "webpylike"))


@click.group()
def cli():
    pass


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
    namespace = dict()
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
