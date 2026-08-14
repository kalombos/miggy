import peewee as pw

from miggy.operations import AddCheckConstraint
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import CheckMeta, extract_check_meta
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

    state = State({"user": User})
    operation = AddCheckConstraint("user", "check_name", "name != 'alice'")
    operation.state_forwards(state)

    assert extract_check_meta(state["user"])[0] == CheckMeta("check_name", "name != 'alice'")


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})
    operation = AddCheckConstraint("user", "check_name", "name != 'alice'")
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    assert patched_pg_db.queries == ['ALTER TABLE "user" ADD CONSTRAINT "check_name" CHECK (name != \'alice\')']
