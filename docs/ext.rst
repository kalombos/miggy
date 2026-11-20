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

.. note::

    **Deprecated.** ``model_factory`` is deprecated and will be removed in a
    future release. Use the ``miggy.ext.peewee_factory`` module
    (``PeeweeFactory``) instead, see :ref:`peewee-polyfactory`.

**model_factory** is a simple helper to create dynamic model instances for testing purposes.

.. automethod:: miggy.ext::model_factory


.. _peewee-polyfactory:

PeeweeFactory
++++++++++++++++++

**PeeweeFactory** is a `polyfactory <https://github.com/litestar-org/polyfactory>`__
factory for Peewee models.
It introspects model fields and generates values for them: field types are
mapped to Python types, ``CharField.max_length`` and ``DecimalField``
constraints are respected, ``ForeignKeyField`` values are built as related
model instances, and playhouse ``EnumField``/``IntEnumField`` are filled with random enum values.

Dependencies
------------

* ``polyfactory`` is required for all factory features. It is installed
  together with Miggy.
* ``create_async`` (async usage) additionally requires ``peewee`` 4.0 or
  newer, ``asyncpg`` and ``greenlet``.

Sync usage
----------

.. literalinclude:: ../examples/peewee_factory/sync_usage.py
   :language: python


Async usage
-----------

.. literalinclude:: ../examples/peewee_factory/pwasyncio_usage.py
   :language: python


Using with peewee-async
-----------------------

If you use `peewee-async <https://github.com/05bit/peewee-async>`__ instead
of ``playhouse.pwasyncio``:

.. literalinclude:: ../examples/peewee_factory/peewee_async_usage.py
   :language: python
