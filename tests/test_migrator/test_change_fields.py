from typing import Any

import peewee as pw
import pytest

from miggy import Migrator
from tests.conftest import PatchedPgDatabase


@pytest.mark.parametrize(
    ("null_before", "null_after", "expected"),
    [
        (
            False,
            True,
            [
                'ALTER TABLE "user" ALTER COLUMN "created_at" TYPE TIMESTAMP',
                'ALTER TABLE "user" ALTER COLUMN "created_at" DROP NOT NULL',
            ],
        ),
        (
            True,
            False,
            [
                'ALTER TABLE "user" ALTER COLUMN "created_at" TYPE TIMESTAMP',
                'ALTER TABLE "user" ALTER COLUMN "created_at" SET NOT NULL',
            ],
        ),
        (
            True,
            True,
            [
                'ALTER TABLE "user" ALTER COLUMN "created_at" TYPE TIMESTAMP',
            ],
        ),
    ],
)
def test_change_nullable(
    null_before: bool, null_after: bool, expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField(null=null_before)

    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", created_at=pw.DateTimeField(null=null_after))
    migrator.run()
    assert patched_pg_db.queries == expected

    assert migrator.state["user"].created_at.null == null_after
    assert isinstance(migrator.state["user"].created_at, pw.DateTimeField)


def test_change_column_name(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", name=pw.TextField(column_name="new_name"))
    migrator.run()
    assert patched_pg_db.queries == [
        'ALTER TABLE "user" RENAME COLUMN "name" TO "new_name"',
        'ALTER TABLE "user" ALTER COLUMN "new_name" TYPE TEXT',
    ]


@pytest.mark.parametrize(
    ("params_before", "params_after", "expected"),
    [
        (
            {"column_name": "also_check_renaming"},
            {"constraints": [pw.SQL("DEFAULT 5")]},
            [
                'ALTER TABLE "user" RENAME COLUMN "also_check_renaming" TO "age"',
                'ALTER TABLE "user" ALTER COLUMN "age" SET DEFAULT 5',
            ],
        ),
    ],
)
def test_change_default_constraints(
    params_before: dict[str, Any], params_after: dict[str, Any], expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        age = pw.IntegerField(**params_before)

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.change_fields("user", age=pw.IntegerField(**params_after))
    migrator.run()

    assert patched_pg_db.queries == expected


@pytest.mark.parametrize(
    ("field_before", "field_after", "expected"),
    [
        pytest.param(pw.IntegerField(), pw.IntegerField(default=7), [], id="apply_default"),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=lambda: 8),
            [],
            id="apply_default_callable",
        ),
        pytest.param(pw.IntegerField(default=7), pw.IntegerField(), [], id="nothing_to_do"),
    ],
)
def test_change_default(
    field_before: pw.Field, field_after: pw.Field, expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        age = field_before

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.change_fields("user", age=field_after)
    migrator.run()

    assert patched_pg_db.queries == expected
