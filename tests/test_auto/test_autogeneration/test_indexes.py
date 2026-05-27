from typing import Any

import peewee as pw
import pytest

from miggy.auto import diff_one
from miggy.types import ModelCls
from miggy.utils import ModelIndex
from tests.helpers import operation_to_one_line


@pytest.mark.parametrize(
    ("before_params", "after_params", "changes"),
    [
        # # Adding index
        (
            {},
            {"index": True, "unique": True},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(unique=True),)"],
        ),
        (
            {},
            {"index": False, "unique": True},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(unique=True),)"],
        ),
        (
            {},
            {"index": True, "unique": False},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(index=True),)"],
        ),
        # Changing index
        (
            {"index": True, "unique": False},
            {"index": True, "unique": True},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(unique=True),)"],
        ),
        (
            {"index": True, "unique": True},
            {"index": True, "unique": False},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(index=True),)"],
        ),
        (
            {"index": False, "unique": True},
            {"index": True, "unique": False},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(index=True),)"],
        ),
        # Dropping index
        (
            {"index": True, "unique": True},
            {},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(),)"],
        ),
        (
            {"index": False, "unique": True},
            {"index": False, "unique": False},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(),)"],
        ),
        (
            {"index": True, "unique": False},
            {},
            ["migrator.alter_field(model_name='test',name='first_name',field=pw.CharField(),)"],
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
    def create_model(params: dict[str, Any]) -> ModelCls:
        class Test(pw.Model):
            first_name = pw.CharField(**params)

        return Test

    diff = diff_one(create_model(after_params), create_model(before_params))
    diff = [operation_to_one_line(o) for o in diff]  # type: ignore

    assert diff == changes


@pytest.mark.parametrize(
    ("indexes_before", "indexes_after", "changes"),
    [
        # Adding indexes
        (
            [],
            [
                (("first_name",), False),
            ],
            ["migrator.add_index('test','first_name',name='test_first_name',)"],
        ),
        (
            [],
            [
                (("first_name",), True),
            ],
            ["migrator.add_index('test','first_name',name='test_first_name',unique=True,)"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), False),
            ],
            ["migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',)"],
        ),
        (
            [],
            [
                (("first_name", "last_name"), True),
            ],
            ["migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',unique=True,)"],
        ),
        # Dropping indexes
        (
            [
                (("first_name", "last_name"), True),
            ],
            [],
            ["migrator.drop_index('test','test_first_name_last_name',)"],
        ),
        (
            [
                (("first_name", "last_name"), False),
            ],
            [],
            ["migrator.drop_index('test','test_first_name_last_name',)"],
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
                "migrator.drop_index('test','test_first_name_last_name',)",
                "migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',unique=True,)",
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

    diffs = diff_one(create_model(indexes_after), create_model(indexes_before))
    assert [operation_to_one_line(d) for d in diffs] == changes  # type: ignore


@pytest.mark.parametrize(
    ("before_kwargs", "after_kwargs", "changes"),
    [
        ({"unique": False}, {"unique": False}, []),
        (
            {"unique": False},
            {"unique": False, "name": "new_name"},
            [
                "migrator.drop_index('test','test_first_name_last_name',)",
                "migrator.add_index('test','first_name','last_name',name='new_name',)",
            ],
        ),
        (
            {"unique": False},
            {"unique": True},
            [
                "migrator.drop_index('test','test_first_name_last_name',)",
                "migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',unique=True,)",
            ],
        ),
        (
            {"where": pw.SQL("first_name = 'bom'")},
            {"unique": False},
            [
                "migrator.drop_index('test','test_first_name_last_name',)",
                "migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',)",
            ],
        ),
        (
            {"unique": False},
            {"where": pw.SQL("first_name = 'bom'")},
            [
                "migrator.drop_index('test','test_first_name_last_name',)",
                """migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',where=pw.SQL("first_name = 'bom'"),)""",  # noqa: E501
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

    diffs = diff_one(create_model(after_kwargs), create_model(before_kwargs))

    assert [operation_to_one_line(d) for d in diffs] == changes  # type: ignore


def test_indexes_rebuilding() -> None:
    def create_model1() -> type[pw.Model]:
        class Test(pw.Model):
            first_name = pw.CharField()
            last_name = pw.CharField()

            class Meta:
                indexes = [
                    (["first_name", "last_name"], False),
                    (["first_name"], False),
                ]

        return Test

    def create_model2() -> type[pw.Model]:
        class Test(pw.Model):
            first_name = pw.CharField()
            last_name = pw.CharField()

        Test._meta.indexes_state = {"test_first_name": ModelIndex(Test, (Test.first_name,))}
        return Test

    changes = diff_one(create_model1(), create_model2())
    assert [operation_to_one_line(c) for c in changes] == [  # type: ignore
        "migrator.add_index('test','first_name','last_name',name='test_first_name_last_name',)"
    ]
