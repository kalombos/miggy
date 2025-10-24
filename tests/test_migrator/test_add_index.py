from typing import Any

import peewee as pw
import pytest

from peewee_migrate import Migrator
from tests.conftest import PatchedPgDatabase


@pytest.mark.parametrize(
    ("patched_pg_db", "index_params", "expected"),
    [
        (
            {"in_transaction": True},
            {"safe": False},
            """CREATE INDEX "some_name" ON "company" ("name") WHERE name='sdfsfad'""",
        ),
        (
            {"in_transaction": True},
            {"safe": True},
            """CREATE INDEX IF NOT EXISTS "some_name" ON "company" ("name") WHERE name='sdfsfad'""",
        ),
        (
            {"in_transaction": False},
            {"concurrently": True},
            """CREATE INDEX CONCURRENTLY "some_name" ON "company" ("name") WHERE name='sdfsfad'""",
        ),
    ],
    indirect=["patched_pg_db"],
)
def test_add_index(patched_pg_db: PatchedPgDatabase, index_params: dict[str, Any], expected: str) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_model
    class Company(pw.Model):
        name = pw.CharField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_index("company", "name", where=pw.SQL("name='sdfsfad'"), name="some_name", **index_params)

    migrator.run()
    assert patched_pg_db.queries == [expected]

    Company.drop_table(safe=True)
