from collections.abc import Generator
from typing import Any

import peewee as pw
import pytest

from peewee_migrate import Migrator
from tests.conftest import POSTGRES_DSN


class PatchedPgDatabase(pw.PostgresqlDatabase):
    queries: list[str] = []

    def clear_queries(self):
        self.queries = []

    def execute_sql(self, sql, params=None, commit=None):
        self.queries.append(sql)
        return super().execute_sql(sql, params, commit)


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

    migrator.add_index(Order, "identifier", "customer")
    migrator.run()
    assert Order._meta.indexes
    assert not Order.identifier.index

    migrator.drop_index(Order, "identifier", "customer")
    migrator.run()
    assert not Order._meta.indexes

    migrator.remove_fields(Order, "customer")
    migrator.run()
    assert not hasattr(Order, "customer")
    migrator.add_index(Order, "identifier", unique=True)
    migrator.run()
    assert Order.identifier.index
    assert Order.identifier.unique
    assert not Order._meta.indexes

    # TODO fix change_columns
    # migrator.change_columns(Order, identifier=pw.IntegerField(default=0))
    # assert not Order._meta.indexes
    # migrator.run()

    migrator.rename_table("order", "new_name")
    migrator.run()
    assert Order._meta.table_name == "new_name"
    migrator.rename_table("new_name", "order")
    migrator.run()


@pytest.fixture()
def patched_pg_db() -> Generator[PatchedPgDatabase, Any, None]:
    db = PatchedPgDatabase(POSTGRES_DSN)
    with db.transaction() as transaction:
        yield db
        transaction.rollback()
    db.close()


def test_create_table(patched_pg_db: PatchedPgDatabase) -> None:
    """
    Ensure change_fields generates queries and
    does not cause exception
    """
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    assert User == migrator.orm["user"]
    migrator.run()
    assert patched_pg_db.queries == [
        'CREATE TABLE IF NOT EXISTS "user" ("id" SERIAL NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL, '
        '"created_at" DATE NOT NULL)'
    ]


@pytest.mark.parametrize(
    ("columns", "unique", "where", "expected"),
    [
        (
            ("name",),
            False,
            None,
            'CREATE INDEX IF NOT EXISTS "user_name" ON "user" (name)',
        ),
        (
            ("name", "created_at"),
            True,
            None,
            'CREATE UNIQUE INDEX IF NOT EXISTS "user_name_created_at" ON "user" (name, created_at)',
        ),
        (
            ("name",),
            False,
            pw.SQL("name = 'John'"),
            """CREATE INDEX IF NOT EXISTS "user_name" ON "user" (name) WHERE name = 'John'""",
        ),
    ],
)
def test_migrator_add_index(
    patched_pg_db: PatchedPgDatabase, columns: tuple[str, ...], unique: bool, where: pw.SQL | None, expected: str
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_index("user", *columns, unique=unique, where=where)
    migrator.run()
    assert patched_pg_db.queries == [expected]


def test_change_datetime_field(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    assert User == migrator.orm["user"]

    # Date -> DateTime
    migrator.change_fields("user", created_at=pw.DateTimeField())
    migrator.run()
    assert 'ALTER TABLE "user" ALTER COLUMN "created_at" TYPE TIMESTAMP' in patched_pg_db.queries


def test_change_text_field(patched_pg_db: PatchedPgDatabase) -> None:
    """
    Ensure change_fields generates queries and
    does not cause exception
    """

    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    assert User == migrator.orm["user"]

    # Char -> Text
    migrator.change_fields("user", name=pw.TextField())
    migrator.run()
    assert 'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT' in patched_pg_db.queries


def test_migrator_schema(patched_pg_db):
    schema_name = "test_schema"
    patched_pg_db.execute_sql("CREATE SCHEMA IF NOT EXISTS test_schema;")

    migrator = Migrator(patched_pg_db, schema=schema_name)

    patched_pg_db.clear_queries()

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()

    assert patched_pg_db.queries[0] == "SET search_path TO {}".format(schema_name)

    patched_pg_db.clear_queries()
    migrator.change_fields("user", created_at=pw.DateTimeField())
    migrator.run()

    assert patched_pg_db.queries[0] == "SET search_path TO {}".format(schema_name)
