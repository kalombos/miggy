import peewee as pw

from miggy.operations import AddPrimaryKeyConstraint
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

    state = State({"user": User})
    operation = AddPrimaryKeyConstraint("user", "name", "email")
    operation.state_forwards(state)

    pk = state["user"]._meta.primary_key
    assert isinstance(pk, pw.CompositeKey)
    assert pk.field_names == ("name", "email")


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            database = patched_pg_db
            primary_key = False

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})
    operation = AddPrimaryKeyConstraint("user", "name", "email")
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    assert patched_pg_db.queries == ['ALTER TABLE "user" ADD PRIMARY KEY ("name", "email")']
