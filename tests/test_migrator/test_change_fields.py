from typing import Any

import peewee as pw
import pytest

from miggy import Migrator
from miggy.utils import Default, has_single_index
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

    assert User == migrator.orm["user"]
    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", created_at=pw.DateTimeField(null=null_after))
    migrator.run()
    assert patched_pg_db.queries == expected

    assert migrator.orm["user"].created_at.null == null_after
    assert isinstance(migrator.orm["user"].created_at, pw.DateTimeField)


@pytest.mark.parametrize(
    ("field_before", "field_after", "expected"),
    [
        (
            pw.CharField(),
            pw.CharField(max_length=None),
            ['ALTER TABLE "user" ALTER COLUMN "field" TYPE VARCHAR'],
        ),
        (
            pw.CharField(),
            pw.CharField(),
            [],
        ),
        (
            pw.CharField(),
            pw.CharField(max_length=5),
            ['ALTER TABLE "user" ALTER COLUMN "field" TYPE VARCHAR(5)'],
        ),
        (
            pw.DecimalField(),
            pw.DecimalField(max_digits=4, decimal_places=2),
            ['ALTER TABLE "user" ALTER COLUMN "field" TYPE NUMERIC(4, 2)'],
        ),
    ],
)
def test_change_type(
    field_before: pw.Field, field_after: pw.Field, expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        field = field_before

    assert User == migrator.orm["user"]
    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", field=field_after)
    migrator.run()
    assert patched_pg_db.queries == expected


def test_change_column_name(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    assert User == migrator.orm["user"]
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
            {},
            {"unique": True},
            ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'CREATE UNIQUE INDEX "user_name" ON "user" ("name")'],
        ),
        ({"unique": True}, {}, ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'DROP INDEX "user_name"']),
        (
            {},
            {"index": True},
            ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'CREATE INDEX "user_name" ON "user" ("name")'],
        ),
        ({"index": True}, {}, ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'DROP INDEX "user_name"']),
        (
            {"index": True},
            {"unique": True},
            [
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE UNIQUE INDEX "user_name" ON "user" ("name")',
            ],
        ),
        (
            {"unique": True},
            {"index": True},
            [
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE INDEX "user_name" ON "user" ("name")',
            ],
        ),
        (
            {"unique": True, "column_name": "bom"},
            {"index": True},
            [
                'ALTER TABLE "user" RENAME COLUMN "bom" TO "name"',
                'ALTER INDEX "user_bom" RENAME TO "user_name"',
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE INDEX "user_name" ON "user" ("name")',
            ],
        ),
        (
            {"unique": True},
            {"index": True, "column_name": "bom"},
            [
                'ALTER TABLE "user" RENAME COLUMN "name" TO "bom"',
                'ALTER INDEX "user_name" RENAME TO "user_bom"',
                'ALTER TABLE "user" ALTER COLUMN "bom" TYPE TEXT',
                'DROP INDEX "user_bom"',
                'CREATE INDEX "user_bom" ON "user" ("bom")',
            ],
        ),
    ],
)
def test_change_indexes(
    params_before: dict[str, Any], params_after: dict[str, Any], expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField(**params_before)
        created_at = pw.DateField()

    assert User == migrator.orm["user"]
    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", name=pw.TextField(**params_after))
    migrator.run()
    assert patched_pg_db.queries == expected

    has_index = params_after.get("unique", False) or params_after.get("index", False)
    assert has_single_index(migrator.orm["user"].name) == has_index


class _M1(pw.Model):
    name = pw.CharField()


class _M2(pw.Model):
    name = pw.CharField()


@pytest.mark.parametrize(
    ("change_params", "expected"),
    [
        pytest.param(
            {"non_fk_field": pw.ForeignKeyField(_M1, on_delete="RESTRICT")},
            [
                'ALTER TABLE "testmodel" RENAME COLUMN "non_fk_field" TO "non_fk_field_id"',
                'ALTER TABLE "testmodel" ALTER COLUMN "non_fk_field_id" TYPE INTEGER',
                (
                    'ALTER TABLE "testmodel" ADD CONSTRAINT "fk_testmodel_non_fk_field_id_refs__m1" '
                    'FOREIGN KEY ("non_fk_field_id") REFERENCES "_m1" ("id") ON DELETE RESTRICT'
                ),
                'CREATE INDEX "testmodel_non_fk_field_id" ON "testmodel" ("non_fk_field_id")',
            ],
            id="non_fk_to_fk",
        ),
        pytest.param(
            {"fk_field": pw.ForeignKeyField(_M1)},
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_fk_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT "fk_testmodel_fk_field_id_refs__m1" '
                'FOREIGN KEY ("fk_field_id") REFERENCES "_m1" ("id")',
            ],
            id="fk_to_fk",
        ),
        pytest.param(
            {"fk_field": pw.IntegerField()},
            [
                'ALTER TABLE "testmodel" RENAME COLUMN "fk_field_id" TO "fk_field"',
                'ALTER INDEX "testmodel_fk_field_id" RENAME TO "testmodel_fk_field"',
                'ALTER TABLE "testmodel" ALTER COLUMN "fk_field" TYPE INTEGER',
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_fk_field_id_fkey"',
                'DROP INDEX "testmodel_fk_field"',
            ],
            id="fk_to_integer",
        ),
        pytest.param(
            {"fk_field": pw.ForeignKeyField(_M2, constraint_name="some_name")},
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_fk_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT "some_name" '
                'FOREIGN KEY ("fk_field_id") REFERENCES "_m2" ("id")',
            ],
            id="change_constraint_name",
        ),
        pytest.param(
            {"fk_field": pw.ForeignKeyField(_M2, column_name="some_name")},
            [
                'ALTER TABLE "testmodel" RENAME COLUMN "fk_field_id" TO "some_name"',
                'ALTER INDEX "testmodel_fk_field_id" RENAME TO "testmodel_some_name"',
            ],
            id="change_column_name",
        ),
    ],
)
def test_change_integer_field_to_fk(
    change_params: dict[str, Any], expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    migrator.create_table(_M1)
    migrator.create_table(_M2)

    @migrator.create_table
    class TestModel(pw.Model):
        name = pw.CharField()
        fk_field = pw.ForeignKeyField(_M2)
        non_fk_field = pw.IntegerField()

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.change_fields("testmodel", **change_params)
    migrator.run()

    # remove query for constraints
    queries = [q for q in patched_pg_db.queries if "FROM information_schema.table_constraints" not in q]
    assert queries == expected


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
        (
            {"constraints": [pw.SQL("DEFAULT 5")]},
            {"constraints": [pw.SQL("DEFAULT 5")]},
            [],
        ),
        (
            {"constraints": [pw.SQL("DEFAULT 5")]},
            {},
            ['ALTER TABLE "user" ALTER COLUMN "age" DROP DEFAULT'],
        ),
        (
            {"constraints": [Default("5")]},
            {},
            ['ALTER TABLE "user" ALTER COLUMN "age" DROP DEFAULT'],
        ),
        (
            {},
            {"constraints": [Default("6")]},
            ['ALTER TABLE "user" ALTER COLUMN "age" SET DEFAULT 6'],
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
