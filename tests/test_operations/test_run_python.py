import peewee as pw

from miggy.operations import RunPython
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase
from tests.helpers import run_operations


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    from_state = State({"user": User})

    def save_user(schema_migrator, state):
        user = state["user"]
        user(first_name="First", last_name="Last").save()

    operation = RunPython(save_user)
    run_operations(operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State()))

    assert patched_pg_db.queries == [
        'INSERT INTO "user" ("first_name", "last_name") VALUES (First, Last) RETURNING "user"."id"'
    ]
