from typing import Any

import peewee as pw
import pytest

from miggy import Migrator
from tests.conftest import PatchedPgDatabase


def test_add_fields(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

        class Meta:
            table_name = "some_name"

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", last_name=pw.CharField(null=True, unique=True), age=pw.IntegerField(null=True))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "some_name" ADD COLUMN "last_name" VARCHAR(255)',
        'CREATE UNIQUE INDEX "some_name_last_name" ON "some_name" ("last_name")',
        'ALTER TABLE "some_name" ADD COLUMN "age" INTEGER',
    ]

    last_name = migrator.state["user"].last_name
    assert isinstance(last_name, pw.CharField)
    assert last_name.unique
    assert last_name.null

    age = migrator.state["user"].age
    assert isinstance(age, pw.IntegerField)
    assert age.null


def test_add_fields__default_constraint(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", created_at=pw.DateField(constraints=[pw.SQL("DEFAULT now()")]))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ADD COLUMN "created_at" DATE DEFAULT now()',
        'ALTER TABLE "user" ALTER COLUMN "created_at" SET NOT NULL',
    ]


def test_add_fields__default_value(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("user", age=pw.IntegerField(default=5))
    migrator.run()

    assert patched_pg_db.queries == [
        'ALTER TABLE "user" ADD COLUMN "age" INTEGER',
        'UPDATE "user" SET "age" = 5',
        'ALTER TABLE "user" ALTER COLUMN "age" SET NOT NULL',
    ]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (
            {
                "null": True,
            },
            [
                'ALTER TABLE "author" ADD COLUMN "user_id" INTEGER REFERENCES "user" ("id")',
                'CREATE INDEX "author_user_id" ON "author" ("user_id")',
            ],
        ),
        (
            {"null": True, "on_delete": "CASCADE", "on_update": "RESTRICT", "index": False},
            [
                'ALTER TABLE "author" ADD COLUMN "user_id" INTEGER REFERENCES "user" '
                '("id") ON DELETE CASCADE ON UPDATE RESTRICT',
            ],
        ),
    ],
)
def test_add_fk_field(params: dict[str, Any], expected: list[str], patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()

    @migrator.create_table
    class Author(pw.Model):
        rating = pw.IntegerField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.add_fields("author", user=pw.ForeignKeyField(User, **params))
    migrator.run()

    assert patched_pg_db.queries == expected
