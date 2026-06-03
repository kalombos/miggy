import peewee as pw

from miggy.operations import RemovePrimaryKeyConstraint
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            primary_key = pw.CompositeKey("name", "email")

    state = State({"user": User})
    operation = RemovePrimaryKeyConstraint("user")
    operation.state_forwards(state)

    assert state["user"]._meta.primary_key is False


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            database = patched_pg_db
            primary_key = pw.CompositeKey("name", "email")

    User.create_table()
    patched_pg_db.clear_queries()

    from_state = State({"user": User})
    operation = RemovePrimaryKeyConstraint("user")

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State())[0].run()

    queries = [q for q in patched_pg_db.queries if "FROM pg_constraint" not in q]
    assert queries == ['ALTER TABLE "user" DROP CONSTRAINT "user_pkey"']
