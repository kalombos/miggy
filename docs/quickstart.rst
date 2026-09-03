Quickstart
==========

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
you can use ``miggy rollback`` to revert the changes.

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


And that's it! Miggy has detected the changes and generated the migration
for you.

If you need the complete source code for this example, you can find it on
`GitHub`_.

.. _GitHub: https://github.com/kalombos/miggy/tree/master/examples/quickstart