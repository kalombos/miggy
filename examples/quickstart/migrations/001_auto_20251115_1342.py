"""Peewee migrations -- 001_auto_20251115_1342.py.

Some examples (model - class or model name)::

    # You should not run any database operations without the API calls listed below.

    > migrator.sql(sql, params: tuple[Any, ...] | None = None)    # Run custom SQL
    > migrator.python(func: RunPythonF)                           # Run python code
    > migrator.add_operation(op: MigrateOperation)                # Run custom MigrateOperation
    > migrator.create_model(Model: Model)                         # Create a model (could be used as decorator)
    > migrator.remove_model(model_name: str)                      # Remove a model
    > migrator.add_fields(model_name: str, **fields: pw.Field)    # Add fields to a model
    > migrator.change_fields(model_name: str, **fields: pw.Field) # Change fields
    > migrator.remove_fields(model_name: str, *field_names: pw.Field, cascade: bool = False)
    > migrator.rename_field(model_name: str, old_name: str, new_name: str)
    > migrator.rename_table(model_name: str, new_table_name: str)
    > migrator.add_index(
            model_name: str,
            *fields: str,
            name: str,
            unique: bool = False,
            where: pw.SQL | None = None,
            safe: bool = False,
            concurrently: bool = False
      )
    > migrator.drop_index(model_name: str, name: str)
    > migrator.add_not_null(model_name: str, *field_names: str)
    > migrator.drop_not_null(model_name: str, *field_names: str)

"""

import peewee as pw
import playhouse.postgres_ext as pw_pext

SQL = pw.SQL


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

    migrator.remove_model("user")
