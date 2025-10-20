import peewee as pw

from peewee_migrate import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_create_model(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class Company(pw.Model):
        name = pw.CharField()

    @migrator.create_model
    class User(types.Model):
        check_char_length = pw.CharField(max_length=50)
        check_null = pw.CharField(null=True)
        column_different = pw.IntegerField(column_name="other_column_name")
        check_decimal = pw.DecimalField(max_digits=3, decimal_places=4)
        check_default_constraint = pw.DateField(constraints=[pw.SQL("DEFAULT now()")])
        check_fk = pw.ForeignKeyField(Company, constraint_name="blabla", on_update="RESTRICT", index=False)

    assert User == migrator.orm["user"]

    migrator.run()
    assert patched_pg_db.queries == [
        'CREATE TABLE "company" ("id" SERIAL NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL)',
        'CREATE TABLE "user" ("id" SERIAL NOT NULL PRIMARY KEY, '
        '"check_char_length" VARCHAR(50) NOT NULL, '
        '"check_null" VARCHAR(255), '
        '"other_column_name" INTEGER NOT NULL, '
        '"check_decimal" NUMERIC(3, 4) NOT NULL, '
        '"check_default_constraint" DATE NOT NULL DEFAULT now(), '
        '"check_fk_id" INTEGER NOT NULL, CONSTRAINT "blabla" FOREIGN KEY '
        '("check_fk_id") REFERENCES "company" ("id") ON UPDATE RESTRICT)',
    ]
