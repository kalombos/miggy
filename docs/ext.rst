Extensions
====================

Miggy has extension modules which are collected under the **miggy.ext** namespace.


Enum fields
+++++++++++

Miggy provides classes for working with ``enum`` fields in
Peewee models. These fields are intended to simplify integration with
``enum.StrEnum`` and ``enum.IntEnum``.

It is important to understand that enum fields **do not create native
ENUM types in the database**. They are thin wrappers around
standard Peewee fields:

* ``CharEnumField`` — a wrapper around ``CharField``
* ``IntEnumField`` — a wrapper around ``SmallIntegerField``

Values are stored in the database as plain strings or integers.

Example::

    import enum
    from peewee import Model
    from miggy.ext import CharEnumField, IntEnumField


    class Status(enum.StrEnum):
        NEW = "new"
        IN_PROGRESS = "in_progress"
        DONE = "done"


    class Priority(enum.IntEnum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3


    class Task(Model):
        status = CharEnumField(Status, max_length=32)
        priority = IntEnumField(Priority)


Migrations
----------

Enum fields are fully supported by Miggy migrations.

When migrations are generated, these fields will appear as their
underlying Peewee field types:

* ``CharEnumField`` → ``CharField``
* ``IntegerEnumField`` → ``SmallIntegerField``

API
---
.. autoclass:: miggy.ext.fields::BaseEnumField
.. autoclass:: miggy.ext.fields::CharEnumField
.. autoclass:: miggy.ext.fields::IntEnumField



Model Factory
++++++++++++++++++

**model_factory** is a simple helper to create dynamic model instances for testing purposes.

.. automethod:: miggy.ext::model_factory


Peewee Polyfactory
++++++++++++++++++

**PeeweeFactory** is a `polyfactory <https://github.com/litestar-org/polyfactory>`__
factory for Peewee models.
It introspects model fields and generates values for them: field types are
mapped to Python types, ``CharField.max_length`` and ``DecimalField``
constraints are respected, ``ForeignKeyField`` values are built as related
model instances, and pplayhouse ``EnumField``/``IntEnumField`` are filled with random enum values.

Sync usage::

    from peewee import CharField, ForeignKeyField, Model
    from miggy.ext import PeeweeFactory


    class Author(Model):
        name = CharField(max_length=20)


    class Book(Model):
        title = CharField()
        author = ForeignKeyField(Author, null=True)


    class BookFactory(PeeweeFactory[Book]):
        __allow_none_optionals__ = False


    book = BookFactory.build()              # unsaved instance
    book = BookFactory.create_sync()        # built and saved, FK relations included
    books = BookFactory.create_batch_sync(5)


Async usage requires `playhouse.pwasyncio`: derive the model from
``AsyncModel`` and bind it to an ``AsyncDatabaseMixin`` database
(e.g. ``AsyncPostgresqlDatabase``)::

    import peewee as pw
    from playhouse import pwasyncio
    from miggy.ext import PeeweeFactory


    class AsyncBook(pwasyncio.AsyncModel):
        class Meta:
            database = async_db
        title = pw.CharField()


    class AsyncBookFactory(PeeweeFactory[AsyncBook]):
        __allow_none_optionals__ = False


    book = await AsyncBookFactory.create_async()

.. autoclass:: miggy.ext.polyfactory::PeeweeFactory
    :members: