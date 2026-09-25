import peewee as pw

from miggy import Migrator
from miggy.operations import (
    AddCheckConstraint,
    AddField,
    AddIndex,
    AddPrimaryKeyConstraint,
    AlterField,
    ChangeNullable,
    CreateModel,
    DropIndex,
    MigrateOperation,
    RemoveCheckConstraint,
    RemoveField,
    RemoveModel,
    RemovePrimaryKeyConstraint,
    RenameField,
    RenameTable,
    RunPython,
    RunSql,
)


def test_migrator_starts_empty() -> None:
    assert Migrator().operations == []


def test_add_operation_appends_to_operations() -> None:
    migrator = Migrator()
    op = RunSql("SELECT 1")
    migrator.add_operation(op)

    assert migrator.operations == [op]


def test_python() -> None:
    def save_user(schema_migrator, state):
        pass

    migrator = Migrator()
    migrator.python(save_user)

    op = migrator.operations[0]
    assert isinstance(op, RunPython)
    assert op.func is save_user


def test_sql() -> None:
    migrator = Migrator()
    migrator.sql("SELECT 1", (1,))

    op = migrator.operations[0]
    assert isinstance(op, RunSql)
    assert op.sql == "SELECT 1"
    assert op.params == (1,)


def test_create_model_by_name() -> None:
    migrator = Migrator()
    result = migrator.create_model("company", fields={"name": pw.CharField()}, meta={"table_name": "some_name"})

    assert result is None
    op = migrator.operations[0]
    assert isinstance(op, CreateModel)
    assert op.name == "company"
    assert isinstance(op.fields["name"], pw.CharField)
    assert op.meta == {"table_name": "some_name"}


def test_create_model_by_name_defaults_fields_and_meta() -> None:
    migrator = Migrator()
    migrator.create_model("company")

    op = migrator.operations[0]
    assert isinstance(op, CreateModel)
    assert op.fields == {}
    assert op.meta == {}


def test_create_model_legacy_model_class() -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

    migrator = Migrator()
    result = migrator.create_table(User)

    assert result is User
    op = migrator.operations[0]
    assert isinstance(op, CreateModel)
    assert op.name == "User"
    assert set(op.fields) == {"first_name", "last_name"}
    assert isinstance(op.fields["first_name"], pw.CharField)
    assert op.meta == {}


def test_remove_model() -> None:
    migrator = Migrator()
    migrator.remove_model("user")

    op = migrator.operations[0]
    assert isinstance(op, RemoveModel)
    assert op.model_name == "user"


def test_remove_model_alias_drop_table() -> None:
    migrator = Migrator()
    migrator.drop_table("user")

    op = migrator.operations[0]
    assert isinstance(op, RemoveModel)
    assert op.model_name == "user"


def test_add_field() -> None:
    migrator = Migrator()
    field = pw.CharField(max_length=255, null=True)
    migrator.add_field("user", "email", field)

    op = migrator.operations[0]
    assert isinstance(op, AddField)
    assert op.model_name == "user"
    assert op.name == "email"
    assert op.field is field


def test_add_fields() -> None:
    migrator = Migrator()
    migrator.add_fields("user", last_name=pw.CharField(null=True), age=pw.IntegerField(null=True))

    assert [type(op) for op in migrator.operations] == [AddField, AddField]
    assert [op.name for op in migrator.operations] == ["last_name", "age"]
    assert isinstance(migrator.operations[0].field, pw.CharField)
    assert isinstance(migrator.operations[1].field, pw.IntegerField)


def test_add_fields_alias_add_columns() -> None:
    migrator = Migrator()
    migrator.add_columns("user", age=pw.IntegerField())

    op = migrator.operations[0]
    assert isinstance(op, AddField)
    assert op.name == "age"


def test_alter_field() -> None:
    migrator = Migrator()
    field = pw.CharField(max_length=100)
    migrator.alter_field("user", "first_name", field)

    op = migrator.operations[0]
    assert isinstance(op, AlterField)
    assert op.model_name == "user"
    assert op.name == "first_name"
    assert op.field is field


def test_change_fields() -> None:
    migrator = Migrator()
    migrator.change_fields("user", first_name=pw.CharField(max_length=100), age=pw.IntegerField())

    assert [type(op) for op in migrator.operations] == [AlterField, AlterField]
    assert [op.name for op in migrator.operations] == ["first_name", "age"]


def test_change_fields_alias_change_columns() -> None:
    migrator = Migrator()
    migrator.change_columns("user", age=pw.IntegerField())

    op = migrator.operations[0]
    assert isinstance(op, AlterField)
    assert op.name == "age"


def test_remove_field() -> None:
    migrator = Migrator()
    migrator.remove_field("user", "name")

    (op,) = migrator.operations
    assert isinstance(op, RemoveField)
    assert op.model_name == "user"
    assert op.name == "name"


def test_remove_fields() -> None:
    migrator = Migrator()
    migrator.remove_fields("user", "name", "created_at")

    assert [type(op) for op in migrator.operations] == [RemoveField, RemoveField]
    assert [op.name for op in migrator.operations] == ["name", "created_at"]


def test_remove_fields_alias_drop_columns() -> None:
    migrator = Migrator()
    migrator.drop_columns("user", "name")

    (op,) = migrator.operations
    assert isinstance(op, RemoveField)
    assert op.name == "name"


def test_rename_field() -> None:
    migrator = Migrator()
    migrator.rename_field("user", "first_name", "new_name")

    (op,) = migrator.operations
    assert isinstance(op, RenameField)
    assert op.model_name == "user"
    assert op.old_field_name == "first_name"
    assert op.new_field_name == "new_name"


def test_rename_field_alias_rename_column() -> None:
    migrator = Migrator()
    migrator.rename_column("user", "first_name", "new_name")

    (op,) = migrator.operations
    assert isinstance(op, RenameField)
    assert op.old_field_name == "first_name"
    assert op.new_field_name == "new_name"


def test_rename_table() -> None:
    migrator = Migrator()
    migrator.rename_table("user", "new_name")

    (op,) = migrator.operations
    assert isinstance(op, RenameTable)
    assert op.model_name == "user"
    assert op.new_table_name == "new_name"


def test_rename_table_alias_rename_model() -> None:
    migrator = Migrator()
    migrator.rename_model("user", "new_name")

    (op,) = migrator.operations
    assert isinstance(op, RenameTable)
    assert op.new_table_name == "new_name"


def test_add_index() -> None:
    migrator = Migrator()
    migrator.add_index("user", "first_name", "last_name", name="some_name", unique=True, safe=True)

    (op,) = migrator.operations
    assert isinstance(op, AddIndex)
    assert op.model_name == "user"
    assert op.fields == ("first_name", "last_name")
    assert op.name == "some_name"
    assert op.unique is True
    assert op.safe is True


def test_drop_index() -> None:
    migrator = Migrator()
    migrator.drop_index("user", "some_name")

    (op,) = migrator.operations
    assert isinstance(op, DropIndex)
    assert op.model_name == "user"
    assert op.name == "some_name"


def test_add_not_null() -> None:
    migrator = Migrator()
    migrator.add_not_null("user", "name", "created_at")

    (op,) = migrator.operations
    assert isinstance(op, ChangeNullable)
    assert op.model_name == "user"
    assert op.names == ("name", "created_at")
    assert op.is_null is False


def test_drop_not_null() -> None:
    migrator = Migrator()
    migrator.drop_not_null("user", "name", "created_at")

    (op,) = migrator.operations
    assert isinstance(op, ChangeNullable)
    assert op.model_name == "user"
    assert op.names == ("name", "created_at")
    assert op.is_null is True


def test_add_primary_key_constraint() -> None:
    migrator = Migrator()
    migrator.add_primary_key_constraint("user", "first_name", "last_name")

    (op,) = migrator.operations
    assert isinstance(op, AddPrimaryKeyConstraint)
    assert op.model_name == "user"
    assert op.fields == ("first_name", "last_name")


def test_remove_primary_key_constraint() -> None:
    migrator = Migrator()
    migrator.remove_primary_key_constraint("user")

    (op,) = migrator.operations
    assert isinstance(op, RemovePrimaryKeyConstraint)
    assert op.model_name == "user"


def test_add_check_constraint() -> None:
    migrator = Migrator()
    migrator.add_check_constraint("user", "age_check", "age > 0")

    (op,) = migrator.operations
    assert isinstance(op, AddCheckConstraint)
    assert op.model_name == "user"
    assert op.name == "age_check"
    assert op.constraint == "age > 0"


def test_remove_check_constraint() -> None:
    migrator = Migrator()
    migrator.remove_check_constraint("user", "age_check")

    (op,) = migrator.operations
    assert isinstance(op, RemoveCheckConstraint)
    assert op.model_name == "user"
    assert op.name == "age_check"


def test_shortcuts_keep_operation_order() -> None:
    migrator = Migrator()
    migrator.create_model("user", fields={"name": pw.CharField()})
    migrator.add_field("user", "age", pw.IntegerField(null=True))
    migrator.sql("SELECT 1")

    assert [type(op) for op in migrator.operations] == [CreateModel, AddField, RunSql]


def test_operations_are_migrate_operations() -> None:
    migrator = Migrator()
    migrator.create_model("user", fields={"name": pw.CharField()})
    migrator.remove_model("user")

    assert all(isinstance(op, MigrateOperation) for op in migrator.operations)
