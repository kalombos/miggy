from typing import Any

import peewee as pw
import pytest

from peewee_migrate.auto import diff_one, model_to_code


@pytest.mark.parametrize(
    ("before_params", "after_params", "changes"),
    [
        # # Adding index
        (
            {},
            {"index": True, "unique": True},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255, unique=True))"],
        ),
        (
            {},
            {"index": False, "unique": True},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255, unique=True))"],
        ),
        (
            {},
            {"index": True, "unique": False},
            ["migrator.change_fields('test', first_name=pw.CharField(index=True, max_length=255))"],
        ),
        # Changing index
        (
            {"index": True, "unique": False},
            {"index": True, "unique": True},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255, unique=True))"],
        ),
        (
            {"index": True, "unique": True},
            {"index": True, "unique": False},
            ["migrator.change_fields('test', first_name=pw.CharField(index=True, max_length=255))"],
        ),
        (
            {"index": False, "unique": True},
            {"index": True, "unique": False},
            ["migrator.change_fields('test', first_name=pw.CharField(index=True, max_length=255))"],
        ),
        # Dropping index
        (
            {"index": True, "unique": True},
            {},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255))"],
        ),
        (
            {"index": False, "unique": True},
            {"index": False, "unique": False},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255))"],
        ),
        (
            {"index": True, "unique": False},
            {},
            ["migrator.change_fields('test', first_name=pw.CharField(max_length=255))"],
        ),
        # do nothing
        ({"index": False, "unique": False}, {}, []),
    ],
)
def test_field_index(
    before_params: dict[str, Any],
    after_params: dict[str, Any],
    changes: list[str],
) -> None:
    class _Test(pw.Model):
        first_name = pw.CharField(**before_params)

    class Test(pw.Model):
        first_name = pw.CharField(**after_params)

    assert diff_one(Test, _Test) == changes


@pytest.mark.parametrize(
    ("indexes_before", "indexes_after", "changes"),
    [
        # Adding indexes
        (
            [],
            [
                (("first_name",), False),
            ],
            ["migrator.add_index('test', 'first_name', name='test_first_name')"],
        ),
        (
            [],
            [
                (("first_name",), True),
            ],
            ["migrator.add_index('test', 'first_name', name='test_first_name', unique=True)"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), False),
            ],
            ["migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name')"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), True),
            ],
            ["migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name', unique=True)"],
        ),
        # Dropping indexes
        (
            [
                (("first_name", "last_name"), True),
            ],
            [],
            ["migrator.drop_index('test', 'test_first_name_last_name')"],
        ),
        (
            [
                (("first_name", "last_name"), False),
            ],
            [],
            ["migrator.drop_index('test', 'test_first_name_last_name')"],
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
                "migrator.drop_index('test', 'test_first_name_last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name', unique=True)",
            ],
        ),
        # Nothing to do
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
def test_tuple_indexes__from_meta(indexes_before: list[Any], indexes_after: list[Any], changes: list[str]) -> None:
    def create_model(indexes_: list[Any]) -> type[pw.Model]:
        class Test(pw.Model):
            first_name = pw.CharField()
            last_name = pw.CharField()

            class Meta:
                indexes = indexes_

        return Test

    assert diff_one(create_model(indexes_after), create_model(indexes_before)) == changes


@pytest.mark.parametrize(
    ("before_kwargs", "after_kwargs", "changes"),
    [
        ({"unique": False}, {"unique": False}, []),
        (
            {"unique": False},
            {"unique": False, "name": "new_name"},
            [
                "migrator.drop_index('test', 'test_first_name_last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', name='new_name')",
            ],
        ),
        (
            {"unique": False},
            {"unique": True},
            [
                "migrator.drop_index('test', 'test_first_name_last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name', unique=True)",
            ],
        ),
        (
            {"where": pw.SQL("first_name = 'bom'")},
            {"unique": False},
            [
                "migrator.drop_index('test', 'test_first_name_last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name')",
            ],
        ),
        (
            {"unique": False},
            {"where": pw.SQL("first_name = 'bom'")},
            [
                "migrator.drop_index('test', 'test_first_name_last_name')",
                """migrator.add_index('test', 'first_name', 'last_name', name='test_first_name_last_name', where=pw.SQL("first_name = 'bom'"))""",  # noqa: E501
            ],
        ),
    ],
)
def test_advanced_indexes(before_kwargs: dict[str, Any], after_kwargs: dict[str, Any], changes: list[str]) -> None:
    def create_model(indexes_kwrags: dict[str, Any]) -> type[pw.Model]:
        class Test(pw.Model):
            first_name = pw.CharField()
            last_name = pw.CharField()

        Test.add_index(Test.first_name, Test.last_name, **indexes_kwrags)
        return Test

    assert diff_one(create_model(after_kwargs), create_model(before_kwargs)) == changes


def test_composite_unique_index__create_model():
    class Object(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = ((("first_name", "last_name"), True),)

    code = model_to_code(Object)
    assert code
