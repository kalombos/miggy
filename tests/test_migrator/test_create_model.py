import peewee as pw
import pytest

from peewee_migrate import Migrator
from tests.conftest import PatchedPgDatabase


def test_create_model(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class Company(pw.Model):
        name = pw.CharField()

    @migrator.create_model
    class User(pw.Model):
        check_char_length = pw.CharField(max_length=50)
        check_null = pw.CharField(null=True, index=True)
        column_different = pw.IntegerField(column_name="other_column_name")
        check_decimal = pw.DecimalField(max_digits=3, decimal_places=4)
        check_default_constraint = pw.DateField(constraints=[pw.SQL("DEFAULT now()")])
        check_fk = pw.ForeignKeyField(Company, constraint_name="blabla", on_update="RESTRICT", index=False)

        class Meta:
            table_name = "some_name"

    migrator.add_index(
        "user", "check_char_length", where=pw.SQL("check_char_length='sdfsfad'"), name="some_name_check_char_length"
    )

    migrator.run()
    assert patched_pg_db.queries == [
        'CREATE TABLE "company" ("id" SERIAL NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL)',
        'CREATE TABLE "some_name" ("id" SERIAL NOT NULL PRIMARY KEY, '
        '"check_char_length" VARCHAR(50) NOT NULL, '
        '"check_null" VARCHAR(255), '
        '"other_column_name" INTEGER NOT NULL, '
        '"check_decimal" NUMERIC(3, 4) NOT NULL, '
        '"check_default_constraint" DATE NOT NULL DEFAULT now(), '
        '"check_fk_id" INTEGER NOT NULL, CONSTRAINT "blabla" FOREIGN KEY '
        '("check_fk_id") REFERENCES "company" ("id") ON UPDATE RESTRICT)',
        'CREATE INDEX "some_name_check_null" ON "some_name" ("check_null")',
        (
            """CREATE INDEX "some_name_check_char_length" """
            """ON "some_name" ("check_char_length") WHERE check_char_length='sdfsfad'"""
        ),
    ]


@pytest.mark.parametrize(
    "name",
    ["company", "some_name"],
)
def test_create_model__state(name: str, patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class Company(pw.Model):
        name = pw.CharField()

        class Meta:
            table_name = name

    migrator.run()
    assert Company == migrator.orm["company"]
    assert migrator.orm["company"]._meta.table_name == name
