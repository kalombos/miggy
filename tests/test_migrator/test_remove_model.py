import peewee as pw

from miggy import Migrator, types
from tests.conftest import PatchedPgDatabase


def test_remove_model(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class User(types.Model):
        name = pw.CharField(index=True)
        created_at = pw.DateField()

        class Meta:
            table_name = "what"

    migrator.run()
    assert User == migrator.state["user"]

    patched_pg_db.clear_queries()

    migrator.remove_model("user")
    migrator.run()
    assert patched_pg_db.queries == ['DROP TABLE "what"']

    assert "user" not in migrator.state
