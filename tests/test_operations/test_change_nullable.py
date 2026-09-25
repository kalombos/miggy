import peewee as pw
import pytest

from miggy.operations import ChangeNullable
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards_set_not_null() -> None:
    class User(pw.Model):
        name = pw.CharField(null=True)
        email = pw.CharField(null=True)

    state = State({"user": User})
    operation = ChangeNullable("user", "name", "email", is_null=False)
    operation.state_forwards(state)

    assert state["user"].name.null is False
    assert state["user"].email.null is False


def test_state_forwards_drop_not_null() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

    state = State({"user": User})
    operation = ChangeNullable("user", "name", "email", is_null=True)
    operation.state_forwards(state)

    assert state["user"].name.null is True
    assert state["user"].email.null is True


@pytest.mark.parametrize(
    ("is_null", "expected"),
    [
        (False, 'ALTER TABLE "user" ALTER COLUMN "name" SET NOT NULL'),
        (True, 'ALTER TABLE "user" ALTER COLUMN "name" DROP NOT NULL'),
    ],
)
def test_database_forwards(patched_pg_db: PatchedPgDatabase, is_null: bool, expected: str) -> None:
    initial_null = not is_null

    class User(pw.Model):
        name = pw.CharField(null=initial_null)

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})
    operation = ChangeNullable("user", "name", is_null=is_null)
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    assert patched_pg_db.queries == [expected]
