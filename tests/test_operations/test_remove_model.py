import peewee as pw

from miggy.operations import RemoveModel
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    operation = RemoveModel("user")
    state = State()
    state.add_model(
        "User",
        {
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
        {},
    )
    operation.state_forwards(state)
    assert "user" not in state


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:

    class User(pw.Model):
        name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    operation = RemoveModel("User")
    from_state = State({"user": User})

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State())[0]()

    assert patched_pg_db.queries == [
        'DROP TABLE "user"',
    ]
