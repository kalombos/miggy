"""Peewee migrations -- 003_set_default_age.py.

A migration is a `Migration` class. `forward` and `backward` are lists of
operations from `miggy.operations` to apply forward and backward.
Set `atomic = True` to run the migration inside a single transaction.

Some examples ::

    > operations.RunSql(sql, params: tuple[Any, ...] | None = None)       # Run custom SQL
    > operations.RunPython(func: RunPythonF)                              # Run python code
    > operations.CreateModel(name: str, fields: dict[str, pw.Field], meta: dict[str, Any])
    > operations.RemoveModel(model_name: str)
    > operations.AddField(model_name: str, name: str, field: pw.Field)
    > operations.AlterField(model_name: str, name: str, field: pw.Field)
    > operations.RemoveField(model_name: str, name: str)
    > operations.RenameField(model_name: str, old_name: str, new_name: str)
    > operations.RenameTable(model_name: str, new_table_name: str)
    > operations.AddIndex(
            model_name: str,
            *fields: str,
            name: str,
            unique: bool = False,
            where: pw.SQL | None = None,
            safe: bool = False,
            concurrently: bool = False
      )
    > operations.DropIndex(model_name: str, name: str)
    > operations.AddPrimaryKeyConstraint(model_name: str, *fields: str)
    > operations.RemovePrimaryKeyConstraint(model_name: str)
    > operations.AddCheckConstraint(model_name: str, name: str, constraint: str)
    > operations.RemoveCheckConstraint(model_name: str, name: str)


"""

from miggy import operations


def set_default_age(schema_migrator, state):
    """Set a default value for the `age` field of existing rows."""
    User = state["user"]
    User.update(age=0).where(User.age.is_null()).execute()


class Migration(operations.Migration):
    atomic = True

    forward = [
        operations.RunPython(set_default_age),
    ]

    backward = []
