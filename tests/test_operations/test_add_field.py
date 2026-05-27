import peewee as pw

from miggy.operations import AddField
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:

    class User(pw.Model):
        name = pw.CharField()

    state = State({"user": User})
    operation = AddField("user", "email", pw.CharField())
    operation.state_forwards(state)
    assert isinstance(state["user"].email, pw.CharField)


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:

    class User(pw.Model):
        name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})

    operation = AddField("user", "email", pw.CharField(null=True))
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    queries = patched_pg_db.queries
    assert queries == ['ALTER TABLE "user" ADD COLUMN "email" VARCHAR(255)']
