import peewee as pw

from miggy.operations import RenameTable
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import copy_model
from tests.conftest import PatchedPgDatabase
from tests.helpers import run_operations


def test_state_forwards() -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

    state = State({"user": User})
    operation = RenameTable("user", "new_name")
    operation.state_forwards(state)

    assert state["user"]._meta.table_name == "new_name"


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        first_name = pw.CharField(unique=True)
        last_name = pw.CharField(index=True)

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    from_state = State({"user": User})
    to_state = State({"user": copy_model(User)})
    operation = RenameTable("user", "new_name")
    operation.state_forwards(to_state)

    run_operations(operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, to_state))

    alter_queries = [q for q in patched_pg_db.queries if q.startswith("ALTER ")]
    assert alter_queries == [
        'ALTER TABLE "user" RENAME TO "new_name"',
        'ALTER TABLE "user_id_seq" RENAME TO "new_name_id_seq"',
        'ALTER INDEX "user_first_name" RENAME TO "new_name_first_name"',
        'ALTER INDEX "user_last_name" RENAME TO "new_name_last_name"',
    ]
