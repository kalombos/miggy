Miggy
============


A simple migration engine for **[peewee](https://github.com/coleifer/peewee)**.


[![CI workflow](https://github.com/kalombos/miggy/actions/workflows/tests.yml/badge.svg)](https://github.com/kalombos/miggy/actions/workflows/tests.yml) [![PyPi Version](http://img.shields.io/pypi/v/miggy.svg?style=flat-square)](https://pypi.python.org/pypi/miggy)


Why Fork?
---------

This project is a fork of the original <https://github.com/klen/peewee_migrate> by `klen` — many thanks to them for the initial work!

Since the original project has not been actively maintained for some time, this fork was created to fix critical issues and continue development.

Requirements
------------

-   python >= 3.10
-   peewee>=3.17.9


Installation
------------
    pip install miggy

Usage
-----

### From shell

Getting help:

    $ miggy --help

    Usage: miggy [OPTIONS] COMMAND [ARGS]...

    Options:
        --help  Show this message and exit.

    Commands:
        create   Create migration.
        migrate  Run migrations.
        rollback Rollback migration.

Create migration:

    $ miggy create --help

    Usage: miggy create [OPTIONS] NAME

        Create migration.

    Options:
        --auto                  FLAG  Scan sources and create db migrations automatically. Supports autodiscovery.
        --auto-source           TEXT  Set to python module path for changes autoscan (e.g. 'package.models'). Current directory will be recursively scanned by default.
        --database              TEXT  Database connection
        --directory             TEXT  Directory where migrations are stored
        --schema                TEXT  Database schema
        -v, --verbose
        --help                        Show this message and exit.

Run migrations:

    $ miggy migrate --help

    Usage: miggy migrate [OPTIONS]

        Run migrations.

    Options:
        --name                  TEXT  Select migration
        --database              TEXT  Database connection
        --directory             TEXT  Directory where migrations are stored
        --schema                TEXT  Database schema
        -v, --verbose
        --help                        Show this message and exit.

Auto create migration:

    $ miggy makemigrations --help

    Usage: miggy makemigrations [OPTIONS]

      Create a migration automatically

      Similar to `create` command, but `auto` is True by default, and `name` not
      required

    Options:
        --name TEXT         Migration file name. By default will be
                          'auto_YYYYmmdd_HHMM'
        --auto              Scan sources and create db migrations automatically.
                          Supports autodiscovery.
        --auto-source TEXT  Set to python module path for changes autoscan (e.g.
                          'package.models'). Current directory will be recursively
                          scanned by default.
        --database TEXT     Database connection
        --directory TEXT    Directory where migrations are stored
        --schema                TEXT  Database schema
        -v, --verbose
        --help              Show this message and exit.

### From python

    from miggy import Router
    from peewee import SqliteDatabase

    router = Router(SqliteDatabase('test.db'))

    # Create migration
    router.create('migration_name')

    # Run migration/migrations
    router.run('migration_name')

    # Run all unapplied migrations
    router.run()

### Migration files

By default, migration files are looked up in `os.getcwd()/migrations`
directory, but custom directory can be given.

Migration files are sorted and applied in ascending order per their
filename.

Each migration file must specify `migrate()` function and may specify
`rollback()` function:

    def migrate(migrator, database, fake=False, **kwargs):
        pass

    def rollback(migrator, database, fake=False, **kwargs):
        pass

Bug tracker
-----------

If you have any suggestions, bug reports or annoyances please report
them to the issue tracker at
<https://github.com/kalombos/miggy/issues>

Developing
----------

Install dependencies using pip:

```bash
pip install -e .[dev]
```

Run databases:

```bash
docker-compose up -d
```

Run checks and tests:

```bash
poe check
```

Contributors
------------

See [AUTHORS.md](https://github.com/kalombos/miggy/blob/develop/AUTHORS.md)

License
-------

Licensed under a [BSD license](http://www.linfo.org/bsdlicense.html).
