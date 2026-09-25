import peewee as pw

from miggy.operations import RenameField
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import copy_model
from tests.conftest import PatchedPgDatabase
from tests.helpers import run_operations


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()

    state = State({"user": User})
    operation = RenameField("user", "name", "new_name")
    operation.state_forwards(state)

    assert not hasattr(state["user"], "name")
    assert isinstance(state["user"].new_name, pw.CharField)
    assert state["user"].new_name.column_name == "new_name"


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    from_state = State({"user": User})
    to_state = State({"user": copy_model(User)})

    operation = RenameField("user", "name", "new_name")
    operation.state_forwards(to_state)

    run_operations(operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, to_state))

    assert patched_pg_db.queries == ['ALTER TABLE "user" RENAME COLUMN "name" TO "new_name"']
