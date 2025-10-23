from typing import Any

import peewee as pw
import pytest

from peewee_migrate.auto import (
    IndexMeta,
    IndexMetaExtractor,
    add_index,
    extract_index_meta,
    field_to_code,
    fields_not_equal,
)


class _M1(pw.Model):
    name = pw.CharField()


class _M2(pw.Model):
    name = pw.CharField()


class _DoesNotMatter(pw.Model):
    first_name = pw.CharField()

    class Meta:
        table_name = "table_name"


def test_field_to_code() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])

    assert field_to_code(SomeModel.name) == (
        """name = pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )


@pytest.mark.parametrize(
    ("f1", "f2", "expected"),
    [
        pytest.param(pw.IntegerField(), pw.IntegerField(), False, id="same"),
        pytest.param(pw.IntegerField(), pw.IntegerField(column_name="new_name"), True, id="column"),
        pytest.param(pw.IntegerField(index=True), pw.IntegerField(), True, id="index"),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 5")]), pw.IntegerField(), True, id="default_constraint"
        ),
        pytest.param(pw.IntegerField(default=5), pw.IntegerField(), True, id="default"),
        pytest.param(pw.IntegerField(default=lambda: 5), pw.IntegerField(), False, id="default_callable"),
        pytest.param(pw.IntegerField(), pw.IntegerField(unique=True), True, id="unique"),
        pytest.param(
            pw.IntegerField(index=False, unique=True),
            pw.IntegerField(index=True, unique=True),
            False,
            id="same indexes",
        ),
        pytest.param(pw.IntegerField(), pw.CharField(), True, id="type"),
        pytest.param(pw.CharField(max_length=5), pw.CharField(), True, id="max_length"),
        # FK
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1), False, id="same_fk"),
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M2), True, id="different_models_fk"),
        pytest.param(
            pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1, on_delete="CASCADE"), True, id="different_on_delete_fk"
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, on_update="RESTRICT"), pw.ForeignKeyField(_M1), True, id="different_on_update_fk"
        ),
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1, constraint_name="new_name"), True),
    ],
)
def test_fields_not_equal(f1: pw.Field, f2: pw.Field, expected: bool) -> None:
    assert fields_not_equal(f1, f2) is expected


def test_index_meta_extractor__resolve_where() -> None:
    model_index = pw.ModelIndex(_DoesNotMatter, (_DoesNotMatter.first_name,), where=pw.SQL("first_name = 'bob'"))
    assert IndexMetaExtractor(_DoesNotMatter, model_index).resolve_where(model_index._where) == "first_name = 'bob'"


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
        IndexMetaExtractor(_DoesNotMatter, ("first_name",)).resolve_where(where)


def test_extract_index_meta__tuple() -> None:
    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = [
                (["first_name", "last_name"], False),
            ]

    assert extract_index_meta(Test) == [
        IndexMeta(
            model="test", fields=("first_name", "last_name"), unique=False, where=None, name="test_first_name_last_name"
        )
    ]


def test_extract_index_meta__tuple__unknwon_field() -> None:
    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"
            indexes = [
                (["first_name", "unknwon_field"], False),
            ]

    with pytest.raises(ValueError, match="<Model: Test> does not have 'unknwon_field' field."):
        extract_index_meta(Test)


def test_extract_index_meta__advanced() -> None:
    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

    Test.add_index(Test.first_name, unique=False, name="test_first_name")
    Test.add_index(Test.first_name, Test.last_name, unique=True, where=pw.SQL("first_name = 'bom'"), name="some_name")

    assert extract_index_meta(Test) == [
        IndexMeta(model="test", fields=("first_name",), unique=False, where=None, name="test_first_name"),
        IndexMeta(
            model="test", fields=("first_name", "last_name"), unique=True, where="first_name = 'bom'", name="some_name"
        ),
    ]


def test_extract_index_meta__advanced__str_field_error() -> None:
    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

    Test.add_index("first_name", unique=False, name="test_first_name")
    with pytest.raises(
        NotImplementedError, match="<class 'str'> for ModelIndex.field is not suported. Use Field object instead."
    ):
        extract_index_meta(Test)


@pytest.mark.parametrize(
    ("index_meta", "expected"),
    [
        (
            IndexMeta(model="model", fields=("f1", "f2"), name="some_name"),
            "migrator.add_index('model', 'f1', 'f2', name='some_name')",
        ),
        (
            IndexMeta(
                model="model",
                fields=("f1", "f2"),
                unique=True,
                name="n",
                where="first_name = 'bob'",
            ),
            """migrator.add_index('model', 'f1', 'f2', name='n', unique=True, where=pw.SQL("first_name = 'bob'"))""",
        ),
    ],
)
def test_add_index(index_meta: IndexMeta, expected: str) -> None:
    assert add_index(index_meta) == expected
