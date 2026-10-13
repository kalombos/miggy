from typing import Any

import click


def deprecated_options(func) -> Any:
    func = click.option("--database", default=None, help="Database connection", deprecated=True)(func)

    func = click.option(
        "--directory", default="migrations", help="Directory where migrations are stored", deprecated=True
    )(func)

    func = click.option("--schema", default=None, help="Database schema", deprecated=True)(func)

    func = click.option("-v", "--verbose", count=True, deprecated=True)(func)

    return func



@click.argument("name")
@click.option(
    "--auto",
    default=False,
    is_flag=True,
    help=("Scan sources and create db migrations automatically. Supports autodiscovery."),
)
@click.option(
    "--auto-source",
    default=False,
    help=(
        "Set to python module path for changes autoscan (e.g. 'package.models'). "
        "Current directory will be recursively scanned by default."
    ),
)
@deprecated_options
def create(name, database=None, auto=False, auto_source=False, directory=None, schema=None, verbose=None):
    """Create a migration."""
    from miggy.cli import _load_router
    router = _load_router(directory, database, schema, verbose)
    if auto and auto_source:
        auto = auto_source
    router.create(name, auto=auto)