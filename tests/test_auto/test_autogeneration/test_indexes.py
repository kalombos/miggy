from typing import Any

import peewee as pw
import pytest

from peewee_migrate.auto import IndexMeta, IndexMetaExtractor, add_index, diff_one, extract_index_meta, model_to_code
from peewee_migrate.types import Model


class _DoesNotMatter(Model):
    first_name = pw.CharField()

    class Meta:
        table_name = "table_name"


def test_index_meta_extractor__resolve_where() -> None:
    assert IndexMetaExtractor(_DoesNotMatter).resolve_where(pw.SQL("first_name = 'bob'")) == "first_name = 'bob'"


@pytest.mark.parametrize(
    ("where", "expected_match"),
    [
        (
            "first_name = 'bob'",
            "<class 'str'> for where condition is not suported. Use SQL object without params instead",
        ),
        (
            pw.SQL("first_name = %s", "bob"),
            "SQL object with params for where condition is not suported. Use SQL object without params instead",
        ),
        (
            _DoesNotMatter.first_name == "bob",
            "<class 'peewee.Expression'> for where condition is not suported. Use SQL object without params instead",
        ),
    ],
)
def test_index_meta_extractor__resolve_where__exceptions(where: Any, expected_match: str) -> None:
    with pytest.raises(NotImplementedError, match=expected_match):
        IndexMetaExtractor(_DoesNotMatter).resolve_where(where)


def test_extract_index_meta__tuple() -> None:
    class Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = [
                (["first_name", "last_name"], False),
            ]

    assert extract_index_meta(Test) == [
        IndexMeta(table_name="test", columns=("first_name", "last_name"), unique=False, where=None)
    ]


def test_extract_index_meta__advanced() -> None:
    class Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

    Test.add_index("first_name", unique=False)
    Test.add_index(Test.first_name, Test.last_name, unique=True, where=pw.SQL("first_name = 'bom'"))

    assert extract_index_meta(Test) == [
        IndexMeta(table_name="test", columns=("first_name",), unique=False, where=None),
        IndexMeta(table_name="test", columns=("first_name", "last_name"), unique=True, where="first_name = 'bom'"),
    ]


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
    class _Test(Model):
        first_name = pw.CharField(**before_params)

    class Test(Model):
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
def test_tuple_indexes__from_meta(indexes_before: list[Any], indexes_after: list[Any], changes: list[str]) -> None:
    class _Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = indexes_before

    class Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = indexes_after

    assert diff_one(Test, _Test) == changes


@pytest.mark.parametrize(
    ("before_kwargs", "after_kwargs", "changes"),
    [
        ({"unique": False}, {"unique": False}, []),
        (
            {"unique": False},
            {"unique": True},
            [
                "migrator.drop_index('test', 'first_name', 'last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', unique=True)",
            ],
        ),
        (
            {"where": pw.SQL("first_name = 'bom'")},
            {"unique": False},
            [
                # TODO should be dropped with where condition
                "migrator.drop_index('test', 'first_name', 'last_name')",
                "migrator.add_index('test', 'first_name', 'last_name', unique=False)",
            ],
        ),
        (
            {"unique": False},
            {"where": pw.SQL("first_name = 'bom'")},
            [
                "migrator.drop_index('test', 'first_name', 'last_name')",
                """migrator.add_index('test', 'first_name', 'last_name', unique=False, where=pw.SQL("first_name = 'bom'"))""",  # noqa: E501
            ],
        ),
    ],
)
def test_advanced_indexes(before_kwargs: dict[str, Any], after_kwargs: dict[str, Any], changes: list[str]) -> None:
    class _Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"

    _Test.add_index(_Test.first_name, _Test.last_name, **before_kwargs)

    class Test(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"

    Test.add_index(Test.first_name, Test.last_name, **after_kwargs)

    assert diff_one(Test, _Test) == changes


def test_composite_unique_index__create_model():
    class Object(Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = ((("first_name", "last_name"), True),)

    code = model_to_code(Object)
    assert code
    assert "indexes = [(('first_name', 'last_name'), True)]" in code


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (
            {
                "unique": True,
            },
            "migrator.add_index('table_name', 'column1', unique=True)",
        ),
        (
            {
                "where": "first_name = 'bob'",
            },
            """migrator.add_index('table_name', 'column1', unique=False, where=pw.SQL("first_name = 'bob'"))""",
        ),
    ],
)
def test_add_index(params: dict[str, Any], expected: str) -> None:
    assert add_index(_DoesNotMatter, "column1", **params) == expected
