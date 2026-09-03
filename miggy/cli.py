"""CLI integration."""

import datetime
import shutil
from pathlib import Path

import click

from miggy.compat import deprecated_options
from miggy.router import Router, get_router
from miggy.utils import CONFIG_TEMPLATE


def _load_router(directory, database, schema=None, verbose=0) -> Router:
    ctx = click.get_current_context()
    conf_path = ctx.meta["config_path"]
    if not conf_path.exists():
        click.echo(
            f"{conf_path} is not found. The old config location (conf.py in the "
            "migrations directory) and passing configuration parameters via the CLI "
            "are deprecated. Please run `miggy init` to create a new config."
        )
        conf_path = None

    return get_router(directory, database, schema, verbose, conf_path)


@click.group()
@click.option(
    "--config",
    envvar="MIGGY_CONFIG",
    show_envvar=True,
    type=click.Path(path_type=Path, resolve_path=True),
    default=Path("miggyconf.py"),
    help="Path to the config file. Defaults to miggyconf.py in the current directory.",
)
@click.pass_context
def cli(ctx, config: Path) -> None:
    ctx.meta["config_path"] = config


@cli.command()
def init() -> None:
    """Create a default configuration file."""
    ctx = click.get_current_context()
    conf_path = ctx.meta["config_path"].resolve()
    if conf_path.exists():
        raise click.ClickException(f"{conf_path} already exists")

    conf_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(CONFIG_TEMPLATE, conf_path)
    click.echo(f"Created {conf_path}")


@cli.command()
@click.option(
    "--name",
    default=None,
    help=("Migration file name. By default will be 'auto_YYYYmmdd_HHMM'"),
)
@click.option(
    "--auto",
    default=True,
    is_flag=True,
    help=("Scan sources and create db migrations automatically. Supports autodiscovery."),
)
@click.option(
    "--auto-source",
    default=None,
    help=(
        "Set to python module path for changes autoscan (e.g. 'package.models'). "
        "Current directory will be recursively scanned by default."
    ),
)
@deprecated_options
def makemigrations(
    name=None, database=None, auto=True, auto_source=False, directory=None, schema=None, verbose=None
) -> None:
    """Create a migration automatically

    Similar to `create` command, but `auto` is True by default, and `name` not required
    """
    if name is None:
        name = "auto_{0:%Y%m%d_%H%M}".format(datetime.datetime.now())  # noqa: DTZ005

    router = _load_router(directory, database, schema, verbose)

    if auto and auto_source:
        auto = auto_source
    name = router.create(name, auto=auto)
    if name:
        click.echo(f"Migration created: {name}")


@cli.command()
@click.option("--name", default=None, help="Select migration")
@click.option("--fake", is_flag=True, default=False, help="Run migration as fake.")
@deprecated_options
def migrate(name=None, database=None, directory=None, schema=None, verbose=None, fake=False):
    """Migrate database."""
    router = _load_router(directory, database, schema, verbose)
    migrations = router.run(name, fake=fake)
    if migrations:
        click.echo("Migrations completed: %s" % ", ".join(migrations))


@cli.command()
@click.argument("name", required=False)
@click.option(
    "--count",
    required=False,
    default=1,
    type=int,
    help="Number of last migrations to be rolled back.Ignored in case of non-empty name",
)
@deprecated_options
def rollback(name, count, database=None, directory=None, schema=None, verbose=None):
    """
    Rollback a migration with given name or number of last migrations
    with given --count option as integer number
    """
    router = _load_router(directory, database, schema, verbose)
    if not name:
        if len(router.done) < count:
            raise RuntimeError("Unable to rollback %s migrations from %s: %s" % (count, len(router.done), router.done))
        for _ in range(count):
            router = _load_router(directory, database, schema, verbose)
            name = router.done[-1]
            router.rollback(name)
    else:
        router.rollback(name)


@cli.command()
@deprecated_options
def list(database=None, directory=None, schema=None, verbose=None):  # noqa: A001
    """List migrations."""
    router = _load_router(directory, database, schema, verbose)
    click.echo("Migrations are done:")
    click.echo("\n".join(router.done))
    click.echo("")
    click.echo("Migrations are undone:")
    click.echo("\n".join(router.diff))


# Candidates for deprecation


@cli.command()
@deprecated_options
def merge(database=None, directory=None, schema=None, verbose=None):
    """Merge migrations into one."""
    router = _load_router(directory, database, schema, verbose)
    router.merge()


@cli.command()
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
    router = _load_router(directory, database, schema, verbose)
    if auto and auto_source:
        auto = auto_source
    router.create(name, auto=auto)
