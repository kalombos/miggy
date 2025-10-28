Peewee Migrate 2
============


A simple migration engine for **[peewee](https://github.com/coleifer/peewee)**.


[![CI workflow](https://github.com/kalombos/peewee_migrate2/actions/workflows/tests.yml/badge.svg)](https://github.com/kalombos/peewee_migrate2/actions/workflows/tests.yml) [![PyPi Version](http://img.shields.io/pypi/v/peewee_migrate2.svg?style=flat-square)](https://pypi.python.org/pypi/peewee_migrate2)


Why Fork?
---------

It's a fork of original <https://github.com/klen/peewee_migrate>. Thank
`klen` for that!

But `klen` does not support project for a long time.

To fix critical issues project was forked and development continued.

Requirements
------------

-   python >= 3.10
-   peewee>=3.17.9


Installation
------------

To reduce code changes Python package name don\'t changed. Only name on
PyPI.

If you have installed previous version please remove it before using
pip: :

    pip uninstall peewee_migrate

**Peewee Migrate** should be installed using pip: :

    pip install peewee_migrate2

Usage
-----

### From shell

Getting help:

    $ pw_migrate --help

    Usage: pw_migrate [OPTIONS] COMMAND [ARGS]...

    Options:
        --help  Show this message and exit.

    Commands:
        create   Create migration.
        migrate  Run migrations.
        rollback Rollback migration.

Create migration:

    $ pw_migrate create --help

    Usage: pw_migrate create [OPTIONS] NAME

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

    $ pw_migrate migrate --help

    Usage: pw_migrate migrate [OPTIONS]

        Run migrations.

    Options:
        --name                  TEXT  Select migration
        --database              TEXT  Database connection
        --directory             TEXT  Directory where migrations are stored
        --schema                TEXT  Database schema
        -v, --verbose
        --help                        Show this message and exit.

Auto create migration:

    $ pw_migrate makemigrations --help

    Usage: pw_migrate makemigrations [OPTIONS]

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

    from peewee_migrate import Router
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
<https://github.com/kalombos/peewee_migrate2/issues>

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

See [AUTHORS.md](https://github.com/kalombos/peewee_migrate2/blob/develop/AUTHORS.md)

License
-------

Licensed under a [BSD license](http://www.linfo.org/bsdlicense.html).
