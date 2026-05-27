import peewee as pw

from miggy.operations import RemoveField
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:

    class User(pw.Model):
        name = (pw.CharField(),)
        email = pw.CharField()

    state = State({"user": User})
    operation = RemoveField("user", "email")
    operation.state_forwards(state)
    assert not hasattr(state["user"], "email")


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:

    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    operation = RemoveField("user", "email")
    from_state = State({"user": User})

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State())[0].run()

    queries = [q for q in patched_pg_db.queries if "ccu.constraint_name" not in q]
    assert queries == ['ALTER TABLE "user" DROP COLUMN "email"']
