"""
    Manage Cup Of Tee
    ~~~~~~~~~~~~~~~~~

    Manage the cup of tee application.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import click
from werkzeug.serving import run_simple


def make_app():
    from cupoftee import make_app

    return make_app("/tmp/cupoftee.db")


@click.group()
def cli():
    pass


@cli.command()
@click.option("-h", "--hostname", type=str, default="localhost", help="localhost")
@click.option("-p", "--port", type=int, default=5000, help="5000")
@click.option("--reloader", is_flag=True, default=False)
@click.option("--debugger", is_flag=True)
@click.option("--evalex", is_flag=True, default=False)
@click.option("--threaded", is_flag=True)
@click.option("--processes", type=int, default=1, help="1")
def runserver(hostname, port, reloader, debugger, evalex, threaded, processes):
    """Start a new development server."""
    app = make_app()
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


if __name__ == "__main__":
    cli()
