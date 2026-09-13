from typing import Any

import peewee as pw
import pytest

from miggy.operations import RunSql
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase
from tests.helpers import run_operations


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ('INSERT INTO "user" ("first_name", "last_name") VALUES (\'First\', \'Last\')', None),
        ('INSERT INTO "user" ("first_name", "last_name") VALUES (%s, %s)', ("First", "Last")),
    ],
)
def test_database_forwards(
    patched_pg_db: PatchedPgDatabase,
    sql: str,
    params: tuple[Any, ...] | None,
) -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()

    from_state = State({"user": User})
    operation = RunSql(sql, params)

    run_operations(operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, State()))

    assert User.get(first_name="First", last_name="Last") is not None
