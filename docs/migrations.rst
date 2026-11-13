Migrations
==========

Migrations are Miggy's way of propagating the changes you make to your
models (adding a field, removing a model, etc.) into your database schema.
Think of migrations as a version control system for your database schema:
``makemigrations`` packages your model changes into individual migration
files, analogous to commits, and ``migrate`` applies those files to the
database.

Migration files are plain Python files. You should make them once on your
development machine, commit them to version control together with the model
changes, and run the same migrations on your colleagues' machines, staging,
and eventually production.


The Commands
------------

Miggy provides the following commands:

* ``miggy init`` — create a default configuration file.
* ``miggy makemigrations`` — create a migration automatically.
* ``miggy migrate`` — apply the pending migrations to the database.
* ``miggy rollback`` — roll back the last applied migration.
* ``miggy list`` — list the applied and pending migrations.
* ``miggy squash`` — squash all migrations into a single file.

All commands read their settings from the ``miggyconf.py`` file in the
current directory. The location of the config file can be overridden with
the ``--config`` option or the ``MIGGY_CONFIG`` environment variable.
See :doc:`cli` for the full command reference.


Workflow
--------

Assume that ``quickstart`` is the root directory of our project.

Inside it, create a directory named ``app``. Add a ``models.py`` file
containing our models, and don't forget to include an ``__init__.py`` file::

    import peewee as pw

    from playhouse.postgres_ext import DateTimeTZField, PostgresqlExtDatabase

    POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"

    database = PostgresqlExtDatabase(POSTGRES_DSN)


    class BaseModel(pw.Model):
        created_at = DateTimeTZField(constraints=[pw.SQL("DEFAULT now()")])

        class Meta:
            database = database


    class User(BaseModel):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            database = database


Now let's configure Miggy. Run ``miggy init`` to create the configuration
file, then edit ``miggyconf.py``:

.. literalinclude:: ../examples/quickstart/miggyconf.py
   :language: python


That's it! Now you can run ``miggy makemigrations`` to generate your first
migration:

.. literalinclude:: ../examples/quickstart/migrations/001_auto_20260903_1414.py
   :language: python


Now run ``miggy migrate`` to apply the migration to the database. If needed,
you can use ``miggy rollback`` to revert the changes, and ``miggy list`` to
see the state of your migrations.

Let's change our model a bit::

    class User(BaseModel):
        first_name = pw.CharField()
        last_name = pw.CharField(index=True)
        age = pw.IntegerField(null=True)

        class Meta:
            database = database


Run ``miggy makemigrations`` again to generate a new migration:

.. literalinclude:: ../examples/quickstart/migrations/002_auto_20260903_1414.py
   :language: python
   :start-at: from miggy import operations


And that's it! Miggy has detected the changes and generated the migration
for you.

If you need the complete source code for this example, you can find it on
`GitHub`_.

.. _GitHub: https://github.com/kalombos/miggy/tree/master/examples/quickstart


Transactions
------------

By default, each migration is applied inside a single database transaction —
the generated files contain the ``atomic = True`` attribute. If any
operation fails, all the changes made by that migration are rolled back,
including the record in the ``migratehistory`` table, so a failed migration
is never marked as applied.

Some databases don't support DDL statements inside transactions (e.g.
MySQL). Set ``atomic = False`` in the migration file to run it without a
transaction:

.. code-block:: python

    class Migration(operations.Migration):
        atomic = False

        forward = [
            ...
        ]


Migration Files
---------------

Migration files live in the ``migrations`` directory (configurable with the
``MIGRATE_DIR`` setting). The file name determines the order in which
migrations are applied, so it starts with a three-digit number:
``001_initial.py``, ``002_add_age.py``, and so on.

A migration file defines a single ``Migration`` class. The ``forward`` and
``backward`` attributes are lists of operations to apply when migrating
forwards and rolling back:

.. literalinclude:: ../examples/quickstart/migrations/001_auto_20260903_1414.py
   :language: python
   :start-at: from miggy import operations


The class also supports the following attributes:

* ``atomic`` — run the migration inside a single transaction.
  See the `Transactions`_ section.
* ``fake_initial`` — fake-apply the migration if all its tables already
  exist. Only works for the first migration.
* ``squash`` — fake-apply the migration if the migration history is not
  empty. Only works for the first migration.

Model names in operations are case-insensitive, so
``operations.RemoveModel('user')`` and ``operations.RemoveModel('User')``
are equivalent.

You should rarely need to edit migration files by hand, but it's entirely
possible — some operations cannot be auto-detected and are only available
in hand-written migrations. To create an empty migration for manual
editing, use the ``--empty`` option::

    $ miggy makemigrations --empty --name data_migration


Data migrations
~~~~~~~~~~~~~~~

As well as changing the database schema, you can use migrations to change
the data in the database itself. Such migrations are called "data
migrations". Miggy can't generate them for you, but they are easy to write
by hand.

Let's say the ``age`` column added in migration ``002`` is ``NULL`` for
existing rows and we want to backfill it. Create an empty migration and add
a ``RunPython`` operation:

.. literalinclude:: ../examples/quickstart/migrations/003_set_default_age.py
   :language: python
   :start-at: from miggy import operations


The function passed to ``RunPython`` receives two arguments: a
:class:`~miggy.schema.SchemaMigrator` instance and the historical
:class:`~miggy.state.State` of the models at this point in the migration
history. Use the state instead of importing your models directly, so the
migration keeps working when it is re-applied on a fresh installation.

If you need to run raw SQL, use ``RunSql``:

.. code-block:: python

    operations.RunSql(
        "UPDATE user SET age = 0 WHERE age IS NULL",
    )

.. note::

    Rolling back a data migration doesn't undo the data changes — Miggy has
    no way to know how to reverse arbitrary Python code. If you need a
    backward data migration, add a ``RunPython`` operation to the
    ``backward`` list.

See :doc:`api` for the full list of available operations.


Squashing
---------

Over time, the number of migration files in a project may grow, which can
gradually increase the time required to generate new migrations. You can
reduce the existing set of migrations down to a single file with the
``miggy squash`` command::

    $ miggy squash
    This will delete all existing migration files and squash them into a
    single migration. Continue? [y/N] y


The command deletes all migration files and creates a single
``001_squashed.py`` that describes the current state of the schema. The
``migratehistory`` table is updated accordingly and contains only the
squashed migration:

.. literalinclude:: ../examples/squash/001_squashed.py
   :language: python
   :start-at: from miggy import operations


The squashed migration has the ``squash = True`` attribute. When it is
applied, Miggy checks the migration history: if it contains any records,
the migration is fake-applied and only recorded in the history, otherwise
the schema is created from scratch. This way new installations start from a
single migration, while existing databases keep working.

Keep the following in mind:

* Run ``miggy migrate`` before ``miggy squash`` — unapplied migration files
  are deleted and will be lost.
* Only schema changes are squashed. Custom operations such as ``RunPython``
  and ``RunSql`` from the old migrations are not carried over to the new
  file.


Existing database
-----------------

If you already have a project with an existing schema, you can easily
integrate Miggy. The initial migration should describe the current state of
your database and be fake-applied — recorded in the ``migratehistory``
table without touching the schema.

Assume your models in ``app/models.py`` match the current database schema.
Run ``miggy makemigrations`` with the ``--fake-initial`` flag::

    $ miggy makemigrations --fake-initial
    Migration created: 001_initial


This creates the first migration with the ``fake_initial = True``
attribute:

.. literalinclude:: ../examples/existing_database/001_initial.py
   :language: python
   :start-at: class Migration


Now run ``miggy migrate``. Miggy detects that all the tables from the
initial migration already exist and fake-applies the migration — the schema
is left untouched, and the migration is marked as applied.

.. note::

    Make sure the current database schema matches your models before using
    ``--fake-initial``. Miggy only checks that the tables exist, it doesn't
    verify columns or constraints.

The same effect can be achieved by setting ``fake_initial = True`` manually
in the first migration. From that point on you can use the regular
workflow: change your models, run ``miggy makemigrations`` and
``miggy migrate``.


Psycopg 3
---------

If you use Psycopg 3 as your PostgreSQL driver, you should configure it to
use ``ClientCursor`` when running migrations.

By default, Psycopg 3 sends the query parameters to the server for binding
(server-side binding). PostgreSQL cannot determine the type of a parameter
in certain statements, particularly DDL statements such as
``ALTER TABLE ... SET DEFAULT`` and ``SET search_path``, so migrations may
fail with errors such as::

    psycopg.errors.IndeterminateDatatype:
        could not determine data type of parameter $1

To avoid this issue, use ``psycopg.ClientCursor``, which performs
client-side parameter binding and provides behavior similar to Psycopg 2.
Configure your database in ``miggyconf.py`` as follows:

.. code-block:: python

    import psycopg

    from peewee import PostgresqlDatabase

    DATABASE = PostgresqlDatabase(
        "dbname",
        user="user",
        password="password",
        host="localhost",
        port=5432,
        cursor_factory=psycopg.ClientCursor,
    )
