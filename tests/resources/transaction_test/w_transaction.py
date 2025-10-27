"""Peewee migrations -- 001_test.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['model_name']            # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.python(func, *args, **kwargs)        # Run python code
    > migrator.create_model(Model: Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model: str | Model)    # Remove a model
    > migrator.add_fields(model: str | Model, **fields: pw.Field)          # Add fields to a model
    > migrator.change_fields(model: str | Model, **fields: pw.Field)       # Change fields
    > migrator.remove_fields(model: str | Model, *field_names: pw.Field, cascade: bool = False)
    > migrator.rename_field(model: str | Model, old_name: str, new_name: str)
    > migrator.rename_table(model: str | Model, new_table_name: str)
    > migrator.add_index(model: str | Model, *fields: str, name: str, unique: bool = False, where: pw.SQL | None = None)
    > migrator.drop_index(model: str | Model, name: str)
    > migrator.add_not_null(model: str | Model, *field_names: str)
    > migrator.drop_not_null(model: str | Model, *field_names: str)

"""

import peewee as pw

SQL = pw.SQL


__ATOMIC = True


def migrate(migrator, database, fake=False):
    """Write your migrations here."""

    @migrator.create_model
    class Tag(pw.Model):
        tag = pw.CharField()


def rollback(migrator, database, fake=False):
    """Write your rollback migrations here."""
    pass
