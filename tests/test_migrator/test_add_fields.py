import peewee as pw

from peewee_migrate import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_add_fields(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", last_name=pw.CharField(null=True, unique=True), age=pw.IntegerField(null=True))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ADD COLUMN "last_name" VARCHAR(255)',
        'CREATE UNIQUE INDEX "user_last_name" ON "user" ("last_name")',
        'ALTER TABLE "user" ADD COLUMN "age" INTEGER',
    ]

    last_name = migrator.orm["user"].last_name
    assert isinstance(last_name, pw.CharField)
    assert last_name.unique
    assert last_name.null

    age = migrator.orm["user"].age
    assert isinstance(age, pw.IntegerField)
    assert age.null


def test_add_fields__default_constraint(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", created_at=pw.DateField(constraints=[pw.SQL("DEFAULT now()")]))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ADD COLUMN "created_at" DATE DEFAULT now()',
        'ALTER TABLE "user" ALTER COLUMN "created_at" SET NOT NULL',
    ]


def test_add_fields__default_value(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", age=pw.IntegerField(default=5))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ADD COLUMN "age" INTEGER',
        'UPDATE "user" SET "age" = 5',
        'ALTER TABLE "user" ALTER COLUMN "age" SET NOT NULL',
    ]
