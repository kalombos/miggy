import peewee as pw

from miggy import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_add_not_null(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField(null=True)
        created_at = pw.DateField(null=True)

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_not_null("user", "name", "created_at")
    migrator.run()
    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ALTER COLUMN "name" SET NOT NULL',
        'ALTER TABLE "user" ALTER COLUMN "created_at" SET NOT NULL',
    ]
    assert not migrator.orm["user"].name.null
    assert not migrator.orm["user"].created_at.null


def test_drop_not_null(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.drop_not_null("user", "name", "created_at")
    migrator.run()
    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ALTER COLUMN "name" DROP NOT NULL',
        'ALTER TABLE "user" ALTER COLUMN "created_at" DROP NOT NULL',
    ]
    assert migrator.orm["user"].name.null
    assert migrator.orm["user"].created_at.null
