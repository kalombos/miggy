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
