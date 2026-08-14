import peewee as pw

from miggy.operations import RemoveCheckConstraint
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import extract_check_meta
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            constraints = [pw.Check("name != 'alice'", "check_name")]

    state = State({"user": User})
    operation = RemoveCheckConstraint("user", "check_name")
    operation.state_forwards(state)

    assert extract_check_meta(state["user"]) == []


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

        class Meta:
            database = patched_pg_db
            constraints = [pw.Check("name != 'alice'", "check_name")]

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})
    operation = RemoveCheckConstraint("user", "check_name")
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    assert patched_pg_db.queries == ['ALTER TABLE "user" DROP CONSTRAINT "check_name"']
