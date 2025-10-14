from typing import Any

import peewee as pw
import pytest

from peewee_migrate import Migrator, types
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
    class User(types.Model):
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


def test_change_column_name(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
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
            ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'CREATE UNIQUE INDEX "user_name" ON "user" (name)'],
        ),
        ({"unique": True}, {}, ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'DROP INDEX "user_name"']),
        (
            {},
            {"index": True},
            ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'CREATE INDEX "user_name" ON "user" (name)'],
        ),
        ({"index": True}, {}, ['ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT', 'DROP INDEX "user_name"']),
        (
            {"index": True},
            {"unique": True},
            [
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE UNIQUE INDEX "user_name" ON "user" (name)',
            ],
        ),
        (
            {"unique": True},
            {"index": True},
            [
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE INDEX "user_name" ON "user" (name)',
            ],
        ),
        (
            {"unique": True, "column_name": "bom"},
            {"index": True},
            [
                'ALTER TABLE "user" RENAME COLUMN "bom" TO "name"',
                'ALTER TABLE "user" ALTER COLUMN "name" TYPE TEXT',
                'DROP INDEX "user_bom"',
                'CREATE INDEX "user_name" ON "user" (name)',
            ],
        ),
        (
            {"unique": True},
            {"index": True, "column_name": "bom"},
            [
                'ALTER TABLE "user" RENAME COLUMN "name" TO "bom"',
                'ALTER TABLE "user" ALTER COLUMN "bom" TYPE TEXT',
                'DROP INDEX "user_name"',
                'CREATE INDEX "user_bom" ON "user" (bom)',
            ],
        ),
    ],
)
def test_change_indexes(
    params_before: dict[str, Any], params_after: dict[str, Any], expected: list[str], patched_pg_db: PatchedPgDatabase
) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField(**params_before)
        created_at = pw.DateField()

    assert User == migrator.orm["user"]
    migrator.run()
    patched_pg_db.queries.clear()

    migrator.change_fields("user", name=pw.TextField(**params_after))
    migrator.run()
    assert patched_pg_db.queries == expected
    assert migrator.orm["user"].name.unique == params_after.get("unique", False)


def test_change_fk_field_to_integer(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    @migrator.create_table
    class Book(types.Model):
        name = pw.CharField()
        author = pw.ForeignKeyField(User)

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.change_fields("book", author=pw.IntegerField())
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "book" RENAME COLUMN "author_id" TO "author"',
        'ALTER TABLE "book" ALTER COLUMN "author" TYPE INTEGER',
        'DROP INDEX "book_author_id"',
    ]


def test_change_integer_field_to_fk(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(types.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    @migrator.create_table
    class Book(types.Model):
        name = pw.CharField()
        author = pw.IntegerField()

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.change_fields("book", author=pw.ForeignKeyField(User))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "book" RENAME COLUMN "author" TO "author_id"',
        'ALTER TABLE "book" ALTER COLUMN "author_id" TYPE INTEGER',
        (
            'ALTER TABLE "book" ADD CONSTRAINT "fk_book_author_id_refs_user" '
            'FOREIGN KEY ("author_id") REFERENCES "user" ("id") ON DELETE RESTRICT ON UPDATE RESTRICT'
        ),
        'CREATE INDEX "book_author_id" ON "book" (author_id)',
    ]
