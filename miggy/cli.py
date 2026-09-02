"""CLI integration."""

import datetime
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import click

from miggy.compat import deprecated_options
from miggy.router import Router, add_to_sys_path
from miggy.utils import CONFIG_TEMPLATE, exec_in

VERBOSE = ["WARNING", "INFO", "DEBUG", "NOTSET"]


def get_router(directory, database, schema=None, verbose=0, conf_path: Path | None = None) -> Router:
    from miggy import LOGGER

    logging_level = VERBOSE[verbose]
    config: dict[str, Any] = {}
    migrate_table = "migratehistory"
    working_directory = os.getcwd()
    migrate_dir = directory
    ignore = None
    if conf_path and conf_path.exists():
        working_directory = conf_path.parent.as_posix()
    else:
        # deprecated conf.py
        conf_path = Path(directory) / "conf.py"
    if conf_path.exists():
        # for imports in config
        add_to_sys_path(working_directory)
        with open(conf_path) as cfg:
            exec_in(cfg.read(), config, config)
            database = config.get("DATABASE", database)
            ignore = config.get("IGNORE", ignore)
            schema = config.get("SCHEMA", schema)
            migrate_table = config.get("MIGRATE_TABLE", migrate_table)
            migrate_dir = config.get("MIGRATE_DIR", migrate_dir)
            logging_level = config.get("LOGGING_LEVEL", logging_level).upper()

    LOGGER.setLevel(logging_level)

    try:
        return Router(
            database,
            migrate_table=migrate_table,
            migrate_dir=migrate_dir,
            ignore=ignore,
            schema=schema,
            working_dir=working_directory,
        )
    except RuntimeError as exc:
        LOGGER.error(exc)
        return sys.exit(1)


def _load_router(directory, database, schema=None, verbose=0) -> Router:
    ctx = click.get_current_context()
    return get_router(directory, database, schema, verbose, ctx.meta["config_path"])


@click.group()
@click.option(
    "--config", envvar="MIGGY_CONFIG", type=click.Path(path_type=Path, resolve_path=True), default=Path("miggyconf.py")
)
@click.pass_context
def cli(ctx, config: Path) -> None:
    ctx.meta["config_path"] = config


@cli.command()
def init() -> None:
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


@cli.command()
@deprecated_options
def merge(database=None, directory=None, schema=None, verbose=None):
    """Merge migrations into one."""
    router = _load_router(directory, database, schema, verbose)
    router.merge()
