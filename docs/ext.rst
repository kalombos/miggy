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