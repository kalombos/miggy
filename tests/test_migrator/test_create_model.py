import peewee as pw

from peewee_migrate import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_create_model(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    assert User == migrator.orm["user"]

    migrator.run()
    assert patched_pg_db.queries == [
        'CREATE TABLE "user" ("id" SERIAL NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL, '
        '"created_at" DATE NOT NULL)'
    ]
