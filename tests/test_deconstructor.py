from typing import Any

import peewee as pw
import pytest

from miggy.deconstructor import FieldDeconstructor, ModelDeconstructor, deconstructor_factory, deep_deconstruct
from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.types import ModelCls
from miggy.utils import Default
from tests.helpers import Rating, Status


class _M1(pw.Model):
    name = pw.CharField()


class _M2(pw.Model):
    name = pw.CharField()


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (pw.CharField(max_length=55), {"max_length": 55}),
        (pw.IntegerField(), {}),
        (pw.DecimalField(decimal_places=3), {"decimal_places": 3, "max_digits": 10}),
    ],
)
def test_get_type_modifiers(field: pw.Field, expected: type[pw.Field]) -> None:
    assert deconstructor_factory(field).get_type_modifiers() == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (
            pw.CharField(max_length=55),
            {"column_name": None, "index": (False, False), "type": pw.CharField, "max_length": 55},
        ),
        (pw.IntegerField(), {"column_name": None, "index": (False, False), "type": pw.IntegerField}),
        (
            pw.ForeignKeyField(
                _M1, on_delete="CASCADE", on_update="RESTRICT", constraint_name="constraint_name", null=True
            ),
            {
                "model": "_m1",
                "constraint_name": "constraint_name",
                "column_name": None,
                "index": (True, False),
                "on_delete": "CASCADE",
                "on_update": "RESTRICT",
                "null": True,
                "type": pw.ForeignKeyField,
            },
        ),
    ],
)
def test_field_deconstruct(field: pw.Field, expected: dict[str, Any]) -> None:
    assert deconstructor_factory(field).deconstruct() == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (CharEnumField(Status), pw.CharField),
        (IntEnumField(Rating), pw.SmallIntegerField),
        (pw.CharField(), pw.CharField),
        (pw.SmallIntegerField(), pw.SmallIntegerField),
        (pw.IntegerField(), pw.IntegerField),
    ],
)
def test_deconstructor_get_type(field: pw.Field, expected: type[pw.Field]) -> None:
    assert FieldDeconstructor(field).field_type is expected


@pytest.mark.parametrize(
    ("f1", "f2", "expected"),
    [
        pytest.param(pw.IntegerField(), pw.IntegerField(), False, id="same"),
        pytest.param(pw.IntegerField(), pw.IntegerField(column_name="new_name"), True, id="column"),
        pytest.param(pw.IntegerField(index=True), pw.IntegerField(), True, id="index"),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 5")]), pw.IntegerField(), True, id="default_constraint"
        ),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 5")]),
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 7")]),
            True,
            id="different_default_constraint",
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
def test_deep_deconstruct_not_equal(f1: pw.Field, f2: pw.Field, expected: bool) -> None:
    not_equal = deep_deconstruct(f1) != deep_deconstruct(f2)
    assert not_equal is expected


@pytest.mark.parametrize(
    ("f", "expected"),
    [
        (
            pw.CharField(max_length=50),
            {"max_length": 50, "type": pw.CharField, "column_name": None, "index": (False, False)},
        ),
        (
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 'words'")]),
            {
                "constraints": [{"type": Default, "value": "'words'"}],
                "type": pw.IntegerField,
                "column_name": None,
                "index": (False, False),
            },
        ),
    ],
)
def test_deep_deconstruct(f: pw.Field, expected: dict[str, Any]) -> None:
    assert deep_deconstruct(f) == expected


class _TestModelDeconstructNamespace:
    class SimpleModel(pw.Model):
        name = pw.CharField()

    class ComplicatedModel(pw.Model):
        name = pw.CharField(max_length=5)
        age = pw.IntegerField()

        class Meta:
            schema = "new_schema"
            primary_key = pw.CompositeKey("name", "age")


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (
            _TestModelDeconstructNamespace.SimpleModel,
            {
                "name": "SimpleModel",
                "fields": {
                    "name": {
                        "max_length": 255,
                        "type": pw.CharField,
                        "column_name": "name",
                        "index": (False, False),
                    }
                },
                "meta": {"table_name": "simplemodel"},
            },
        ),
        (
            _TestModelDeconstructNamespace.ComplicatedModel,
            {
                "name": "ComplicatedModel",
                "fields": {
                    "name": {
                        "max_length": 5,
                        "type": pw.CharField,
                        "column_name": "name",
                        "index": (False, False),
                    },
                    "age": {
                        "type": pw.IntegerField,
                        "column_name": "age",
                        "index": (False, False),
                    },
                },
                "meta": {"table_name": "complicatedmodel", "schema": "new_schema", "primary_key": ("name", "age")},
            },
        ),
    ],
)
def test_model_deconstructor__deconstruct(model: ModelCls, expected: dict[str, Any]) -> None:
    deconstructed = ModelDeconstructor(model).deconstruct()
    deconstructed["fields"] = {n: deconstructor_factory(f).deconstruct() for n, f in deconstructed["fields"].items()}
    if "primary_key" in deconstructed["meta"]:
        deconstructed["meta"]["primary_key"] = deconstructed["meta"]["primary_key"].field_names
    assert deconstructed == expected
