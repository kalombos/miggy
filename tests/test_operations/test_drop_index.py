import peewee as pw

from miggy.operations import DropIndex
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import ModelIndex, indexes_state
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()

    state = State({"user": User})
    indexes_state(state["user"])["some_name"] = ModelIndex(state["user"], (state["user"].name,), name="some_name")

    operation = DropIndex("user", "some_name")
    operation.state_forwards(state)

    assert indexes_state(state["user"]) == {}


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.add_index((User.name,), name="some_name")

    User.create_table()
    patched_pg_db.clear_queries()

    from_state = State({"user": User})
    operation = DropIndex("user", "some_name")

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State())[0].run()

    assert patched_pg_db.queries == ['DROP INDEX "some_name"']
