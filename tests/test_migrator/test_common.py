import peewee as pw
import pytest

from peewee_migrate import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_migrator_sqlite_common():
    from playhouse.db_url import connect

    from peewee_migrate import Migrator

    database = connect("sqlite:///:memory:")
    migrator = Migrator(database)

    @migrator.create_table
    class Customer(pw.Model):
        name = pw.CharField()

    assert Customer == migrator.orm["customer"]

    @migrator.create_table
    class Order(pw.Model):
        number = pw.CharField()
        uid = pw.CharField(unique=True)

        customer_id = pw.ForeignKeyField(Customer, column_name="customer_id")

    assert Order == migrator.orm["order"]
    migrator.run()

    migrator.add_columns(Order, finished=pw.BooleanField(default=False))
    assert "finished" in Order._meta.fields
    migrator.run()

    migrator.drop_columns("order", "finished", "customer_id", "uid")
    assert "finished" not in Order._meta.fields
    assert not hasattr(Order, "customer_id")
    assert not hasattr(Order, "customer_id_id")
    migrator.run()

    migrator.add_columns(Order, customer=pw.ForeignKeyField(Customer, null=True))
    assert "customer" in Order._meta.fields
    assert Order.customer.name == "customer"
    migrator.run()
    assert Order.customer.name == "customer"

    migrator.rename_column(Order, "number", "identifier")
    assert "identifier" in Order._meta.fields
    migrator.run()

    migrator.drop_not_null(Order, "identifier")
    assert Order._meta.fields["identifier"].null
    assert Order._meta.columns["identifier"].null
    migrator.run()

    migrator.add_default(Order, "identifier", 11)
    assert Order._meta.fields["identifier"].default == 11
    migrator.run()

    migrator.change_columns(Order, identifier=pw.IntegerField(default=0))
    assert Order.identifier.field_type == "INT"
    migrator.run()

    Order.create(identifier=55)
    migrator.sql('UPDATE "order" SET identifier = 77;')
    migrator.run()
    order = Order.get()
    assert order.identifier == 77

    migrator.add_index(Order, "identifier", "customer", name="some_name")
    migrator.run()
    assert Order._meta.mg_indexes
    assert not Order.identifier.index

    migrator.drop_index(Order, "some_name")
    migrator.run()
    assert not Order._meta.mg_indexes

    migrator.remove_fields(Order, "customer")
    migrator.run()
    assert not hasattr(Order, "customer")
    migrator.add_index(Order, "identifier", unique=True, name="some_name")
    migrator.run()

    assert Order._meta.mg_indexes

    migrator.rename_table("order", "new_name")
    migrator.run()
    assert Order._meta.table_name == "new_name"
    migrator.rename_table("new_name", "order")
    migrator.run()


@pytest.mark.parametrize(
    ("fields", "name", "unique", "where", "expected"),
    [
        (
            ("name",),
            "user_name",
            False,
            None,
            'CREATE INDEX "user_name" ON "user" ("name")',
        ),
        (
            ("name", "created_at"),
            "user_name_created_at",
            True,
            None,
            'CREATE UNIQUE INDEX "user_name_created_at" ON "user" ("name", "created_at")',
        ),
        (
            ("name",),
            "some_name",
            False,
            pw.SQL("name = 'John'"),
            """CREATE INDEX "some_name" ON "user" ("name") WHERE name = 'John'""",
        ),
    ],
)
def test_migrator_add_index(
    patched_pg_db: PatchedPgDatabase,
    fields: tuple[str, ...],
    name: str,
    unique: bool,
    where: pw.SQL | None,
    expected: str,
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_index("user", *fields, name=name, unique=unique, where=where)
    migrator.run()
    assert patched_pg_db.queries == [expected]


def test_migrator_schema(patched_pg_db):
    schema_name = "test_schema"
    patched_pg_db.execute_sql("CREATE SCHEMA IF NOT EXISTS test_schema;")

    migrator = Migrator(patched_pg_db, schema=schema_name)

    patched_pg_db.clear_queries()

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()

    assert patched_pg_db.queries[0] == "SET search_path TO {}".format(schema_name)

    patched_pg_db.clear_queries()
    migrator.change_fields("user", created_at=pw.DateTimeField())
    migrator.run()

    assert patched_pg_db.queries[0] == "SET search_path TO {}".format(schema_name)
