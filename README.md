Miggy
============
[![CI workflow](https://github.com/kalombos/miggy/actions/workflows/tests.yml/badge.svg)](https://github.com/kalombos/miggy/actions/workflows/tests.yml) [![PyPi Version](http://img.shields.io/pypi/v/miggy.svg?style=flat-square)](https://pypi.python.org/pypi/miggy)

A database migration engine for [Peewee](https://github.com/coleifer/peewee), inspired by the architecture of Django migrations.

Miggy builds a state from your migrations and automatically generates a diff against the current model state to create a migration.

Miggy supports detecting changes to most Peewee classes used to define a table, including **fields, indexes, primary keys, DEFAULT and CHECK constraints**.


### New to Miggy?

* [Migrations](https://miggy.readthedocs.io/en/latest/migrations.html)
* [Example app](https://github.com/kalombos/miggy/tree/master/examples/quickstart)
* [Existing database](https://miggy.readthedocs.io/en/latest/migrations.html#existing-database)
* [Read the documentation](https://miggy.readthedocs.io)




### Installation
    pip install miggy


### Why Fork?

Since the original project has not been actively maintained for some time, this project started as a fork of the original [peewee_migrate](https://github.com/klen/peewee_migrate) by `klen` — many thanks to them for the initial work!

Since the fork, the project has been significantly reworked. The architecture has been almost completely redesigned, numerous bugs have been fixed, and support for many Peewee schema features has been added.

Usage
-----

### From shell

Getting help:

    $ miggy --help

    Usage: miggy [OPTIONS] COMMAND [ARGS]...

    Options:
        --config PATH  Path to the config file. Defaults to miggyconf.py in the
                        current directory.  [env var: MIGGY_CONFIG]
        --help         Show this message and exit.

    Commands:
        init            Create a default configuration file.
        list            List migrations.
        makemigrations  Create a migration automatically
        migrate         Migrate database.
        rollback        Rollback a migration with given name or number of last...
        squash          Squash migrations into one.




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

By default, migration files are looked up in the `migrations` directory
next to the config file, but a custom directory can be given with the
`MIGRATE_DIR` setting.

Migration files are sorted and applied in ascending order per their
filename.

Each migration file specifies a `Migration` class with `forward` and
`backward` lists of operations to apply when migrating forwards and
rolling back:

    import peewee as pw
    from miggy import operations

    class Migration(operations.Migration):
        atomic = True

        forward = [
            operations.AddField(
                model_name='user',
                name='age',
                field=pw.IntegerField(null=True),
            ),
        ]

        backward = [
            operations.RemoveField(
                model_name='user',
                name='age',
            ),
        ]



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

License
-------

Licensed under a [BSD license](http://www.linfo.org/bsdlicense.html).
