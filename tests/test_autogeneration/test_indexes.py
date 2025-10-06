from typing import Any

import peewee as pw
import pytest
from playhouse.db_url import connect

from peewee_migrate.auto import diff_one, model_to_code
from peewee_migrate.migrator import Migrator


@pytest.fixture
def migrator() -> Migrator:
    return Migrator(connect("sqlite:///:memory:"))


@pytest.mark.parametrize(
    ("before_params", "after_params", "changes"),
    [
        # Adding index
        ({}, {"index": True, "unique": True}, ["migrator.add_index('test', 'first_name', unique=True)"]),
        ({}, {"index": False, "unique": True}, ["migrator.add_index('test', 'first_name', unique=True)"]),
        ({}, {"index": True, "unique": False}, ["migrator.add_index('test', 'first_name', unique=False)"]),
        # Changing index
        (
            {"index": True, "unique": False},
            {"index": True, "unique": True},
            ["migrator.drop_index('test', 'first_name')", "migrator.add_index('test', 'first_name', unique=True)"],
        ),
        (
            {"index": True, "unique": True},
            {"index": True, "unique": False},
            ["migrator.drop_index('test', 'first_name')", "migrator.add_index('test', 'first_name', unique=False)"],
        ),
        (
            {"index": False, "unique": True},
            {"index": True, "unique": False},
            ["migrator.drop_index('test', 'first_name')", "migrator.add_index('test', 'first_name', unique=False)"],
        ),
        # Dropping index
        ({"index": True, "unique": True}, {}, ["migrator.drop_index('test', 'first_name')"]),
        (
            {"index": False, "unique": True},
            {"index": False, "unique": False},
            ["migrator.drop_index('test', 'first_name')"],
        ),
        ({"index": True, "unique": False}, {}, ["migrator.drop_index('test', 'first_name')"]),
        # do nothing
        ({"index": False, "unique": False}, {}, []),
    ],
)
def test_field_index(
    before_params: dict[str, Any], after_params: dict[str, Any], changes: list[str], migrator: Migrator
) -> None:
    class _Test(pw.Model):
        first_name = pw.CharField(**before_params)

    class Test(pw.Model):
        first_name = pw.CharField(**after_params)

    assert diff_one(Test, _Test, migrator=migrator) == changes


@pytest.mark.parametrize(
    ("indexes_before", "indexes_after", "changes"),
    [
        # Adding indexes
        (
            [],
            [
                (("first_name",), False),
            ],
            ["migrator.add_index('test', 'first_name', unique=False)"],
        ),
        (
            [],
            [
                (("first_name",), True),
            ],
            ["migrator.add_index('test', 'first_name', unique=True)"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), False),
            ],
            ["migrator.add_index('test', 'first_name', 'last_name', unique=False)"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), True),
            ],
            ["migrator.add_index('test', 'first_name', 'last_name', unique=True)"],
        ),
        # Dropping indexes
        (
            [
                (("first_name", "last_name"), True),
            ],
            [],
            ["migrator.drop_index('test', 'first_name', 'last_name')"],
        ),
        (
            [
                (("first_name", "last_name"), False),
            ],
            [],
            ["migrator.drop_index('test', 'first_name', 'last_name')"],
        ),
        # Changing indexes
        (
            [
                (("first_name", "last_name"), False),
            ],
            [
                (("first_name", "last_name"), True),
            ],
            [
                "migrator.drop_index('test', 'first_name', 'last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', unique=True)",
            ],
        ),
        # Changing indexes
        (
            [
                (("first_name", "last_name"), False),
            ],
            [
                (["first_name", "last_name"], False),
            ],
            [],
        ),
    ],
)
def test_tuple_indexes__from_meta(
    indexes_before: list[Any], indexes_after: list[Any], migrator: Migrator, changes: list[str]
) -> None:
    class _Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = indexes_before

    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = indexes_after

    assert diff_one(Test, _Test, migrator=migrator) == changes


def test_composite_unique_index__create_model():
    class Object(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = ((("first_name", "last_name"), True),)

    code = model_to_code(Object)
    assert code
    assert "indexes = [(('first_name', 'last_name'), True)]" in code
