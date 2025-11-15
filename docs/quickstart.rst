Quickstart
====================



Assume that **quickstart** is the root directory of our project. 
Inside it, create a directory named **app**, and within that directory add our models in a file called **models.py**. 
Don't forget to also include an **__init__.py** file::

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

Now we need to configure **Miggy**. To do this, we create a directory named **quickstart/migrations**, and inside it add a file called **conf.py**::

    from app.models import BaseModel, database

    DATABASE = database

    # database.allow_sync() # if you use peewee-async

    IGNORE = [BaseModel._meta.name] # we don't want migrations for abstract model

Thats'it! Now you can run **miggy makemigrations** command and get the first migration::


    import peewee as pw

    import playhouse.postgres_ext as pw_pext

    # Run the migration inside a single transaction
    __ATOMIC = True


    def migrate(migrator, database, fake=False):
        """Write your migrations here."""

        @migrator.create_model
        class User(pw.Model):
            id = pw.AutoField()
            created_at = pw_pext.DateTimeTZField(constraints=[pw.SQL("DEFAULT now()")])
            first_name = pw.CharField(max_length=255)
            last_name = pw.CharField(max_length=255)

            class Meta:
                table_name = "user"

    def rollback(migrator, database, fake=False):
        """Write your rollback migrations here."""

        migrator.remove_model('user')



Now can we run **miggy migrate** and get the changes applied to the database. We can use **miggy rollback** to revert changes if needed. 

Ok let's change our model a bit::

    class User(BaseModel):
        first_name = pw.CharField()
        last_name = pw.CharField(index=True)
        age = pw.IntegerField(null=True)

        class Meta:
            database = database


Run **miggy makemigrations** again to generate the new migration::

    import datetime as dt

    import peewee as pw

    import playhouse.postgres_ext as pw_pext

    SQL = pw.SQL


    # Run the migration inside a single transaction
    __ATOMIC = True


    def migrate(migrator, database, fake=False):
        """Write your migrations here."""

        migrator.add_fields(
            'user',

            age=pw.IntegerField(null=True))

        migrator.change_fields('user', last_name=pw.CharField(index=True, max_length=255))


    def rollback(migrator, database, fake=False):
        """Write your rollback migrations here."""

        migrator.remove_fields('user', 'age')

        migrator.change_fields('user', last_name=pw.CharField(max_length=255))


It has worked again!

If you need the source code of the example you can find it on `GitHub`_.

.. _GitHub: https://github.com/kalombos/miggy/tree/master/examples/quickstart