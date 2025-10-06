""" CLI integration. """
import datetime
import os
import re
import sys

import click
from playhouse.db_url import connect

VERBOSE = ['WARNING', 'INFO', 'DEBUG', 'NOTSET']
CLEAN_RE = re.compile(r'\s+$', re.M)


def get_router(directory, database, schema=None, verbose=0):
    from peewee_migrate import LOGGER
    from peewee_migrate.router import Router
    from peewee_migrate.utils import exec_in

    logging_level = VERBOSE[verbose]
    config = {}
    migrate_table = 'migratehistory'
    ignore = None
    conf_path = os.path.join(directory, 'conf.py')
    if os.path.exists(conf_path):
        with open(conf_path) as cfg:
            exec_in(cfg.read(), config, config)
            database = config.get('DATABASE', database)
            ignore = config.get('IGNORE', ignore)
            schema = config.get('SCHEMA', schema)
            migrate_table = config.get('MIGRATE_TABLE', migrate_table)
            logging_level = config.get('LOGGING_LEVEL', logging_level).upper()

    if isinstance(database, str):
        database = connect(database)

    LOGGER.setLevel(logging_level)

    try:
        return Router(database, migrate_table=migrate_table, migrate_dir=directory,
                      ignore=ignore, schema=schema)
    except RuntimeError as exc:
        LOGGER.error(exc)
        return sys.exit(1)


@click.group()
def cli():
    # allow correctly running from any directory
    # emulate `python -m ...` behaviour
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


@cli.command()
@click.option(
    '--name', default=None, help=(
        'Migration file name. '
        "By default will be 'auto_YYYYmmdd_HHMM'"
    ),
)
@click.option(
    '--auto', default=True, is_flag=True, help=(
        'Scan sources and create db migrations automatically. '
        'Supports autodiscovery.'
    ),
)
@click.option(
    '--auto-source', default=None, help=(
        "Set to python module path for changes autoscan (e.g. 'package.models'). "
        'Current directory will be recursively scanned by default.'
    ),
)
@click.option('--database', default=None, help='Database connection')
@click.option('--directory', default='migrations', help='Directory where migrations are stored')
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def makemigrations(name=None, database=None, auto=True, auto_source=False, directory=None,
                   schema=None, verbose=None):
    """Create a migration automatically

    Similar to `create` command, but `auto` is True by default, and `name` not required
    """
    if name is None:
        name = 'auto_{0:%Y%m%d_%H%M}'.format(datetime.datetime.now())

    router = get_router(directory, database, schema, verbose)
    if auto and auto_source:
        auto = auto_source
    name = router.create(name, auto=auto)
    if name:
        click.echo(f'Migration created: {name}')


@cli.command()
@click.option('--name', default=None, help="Select migration")
@click.option('--database', default=None, help="Database connection")
@click.option('--directory', default='migrations', help="Directory where migrations are stored")
@click.option('--fake', is_flag=True, default=False, help="Run migration as fake.")
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def migrate(name=None, database=None, directory=None, schema=None, verbose=None, fake=False):
    """Migrate database."""
    router = get_router(directory, database, schema, verbose)
    migrations = router.run(name, fake=fake)
    if migrations:
        click.echo('Migrations completed: %s' % ', '.join(migrations))


@cli.command()
@click.argument('name')
@click.option('--auto', default=False, is_flag=True, help=(
    "Scan sources and create db migrations automatically. "
    "Supports autodiscovery."))
@click.option('--auto-source', default=False, help=(
    "Set to python module path for changes autoscan (e.g. 'package.models'). "
    "Current directory will be recursively scanned by default."))
@click.option('--database', default=None, help="Database connection")
@click.option('--directory', default='migrations', help="Directory where migrations are stored")
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def create(name, database=None, auto=False, auto_source=False, directory=None, schema=None,
           verbose=None):
    """Create a migration."""
    router = get_router(directory, database, schema, verbose)
    if auto and auto_source:
        auto = auto_source
    router.create(name, auto=auto)


@cli.command()
@click.argument('name', required=False)
@click.option('--count',
              required=False, 
              default=1, 
              type=int, 
              help="Number of last migrations to be rolled back."
                   "Ignored in case of non-empty name")
@click.option('--database', default=None, help="Database connection")
@click.option('--directory', 
              default='migrations', 
              help="Directory where migrations are stored")
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def rollback(name, count, database=None, directory=None, schema=None, verbose=None):
    """
    Rollback a migration with given name or number of last migrations 
    with given --count option as integer number
    """
    router = get_router(directory, database, schema, verbose)
    if not name:
        if len(router.done) < count:
            raise RuntimeError(
                'Unable to rollback %s migrations from %s: %s' %
                (count, len(router.done), router.done))
        for _ in range(count):
            router = get_router(directory, database, schema, verbose)
            name = router.done[-1]
            router.rollback(name)
    else:
        router.rollback(name)
        

@cli.command()
@click.option('--database', default=None, help="Database connection")
@click.option('--directory', default='migrations', help="Directory where migrations are stored")
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def list(database=None, directory=None, schema=None, verbose=None):
    """List migrations."""
    router = get_router(directory, database, schema, verbose)
    click.echo('Migrations are done:')
    click.echo('\n'.join(router.done))
    click.echo('')
    click.echo('Migrations are undone:')
    click.echo('\n'.join(router.diff))


@cli.command()
@click.option('--database', default=None, help="Database connection")
@click.option('--directory', default='migrations', help="Directory where migrations are stored")
@click.option('--schema', default=None, help='Database schema')
@click.option('-v', '--verbose', count=True)
def merge(database=None, directory=None, schema=None, verbose=None):
    """Merge migrations into one."""
    router = get_router(directory, database, schema, verbose)
    router.merge()
