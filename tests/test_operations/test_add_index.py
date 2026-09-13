from typing import Any

import peewee as pw
import pytest

from miggy.operations import AddIndex
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import indexes_state
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField()

    state = State({"user": User})
    operation = AddIndex("user", "name", "email", name="some_name", unique=True)
    operation.state_forwards(state)

    index = indexes_state(state["user"])["some_name"]
    assert index._name == "some_name"
    assert index._model is state["user"]
    assert index._unique

    assert [e.name for e in index._expressions] == ["name", "email"]


@pytest.mark.parametrize(
    ("fields", "kwargs", "expected"),
    [
        (("name",), {"name": "user_name"}, 'CREATE INDEX "user_name" ON "user" ("name")'),
        (("name",), {"name": "user_name", "unique": True}, 'CREATE UNIQUE INDEX "user_name" ON "user" ("name")'),
        (("name",), {"name": "user_name", "safe": True}, 'CREATE INDEX IF NOT EXISTS "user_name" ON "user" ("name")'),
        (
            ("name",),
            {"name": "user_name", "concurrently": True},
            'CREATE INDEX CONCURRENTLY "user_name" ON "user" ("name")',
        ),
        (
            ("name",),
            {"name": "user_name", "where": pw.SQL("name <> 'alice'")},
            """CREATE INDEX "user_name" ON "user" ("name") WHERE name <> 'alice'""",
        ),
        (
            ("name", "created_at"),
            {"name": "user_name_created_at"},
            'CREATE INDEX "user_name_created_at" ON "user" ("name", "created_at")',
        ),
    ],
)
def test_database_forwards(
    patched_pg_db: PatchedPgDatabase,
    fields: tuple[str, ...],
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    patched_pg_db.clear_queries()

    to_state = State({"user": User})
    operation = AddIndex("user", *fields, **kwargs)
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0].run()

    assert patched_pg_db.queries == [expected]
