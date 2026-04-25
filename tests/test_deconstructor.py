from typing import Any

import peewee as pw
import pytest

from miggy.deconstructor import FieldDeconstructor, ModelDeconstructor, deconstructor_factory
from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.types import ModelCls
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
def test_deconstructor_get_type_params(field: pw.Field, expected: type[pw.Field]) -> None:
    assert deconstructor_factory(field).get_type_modifiers() == expected


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
    not_equal = deconstructor_factory(f1).deconstruct() != deconstructor_factory(f2).deconstruct()
    assert not_equal is expected


class _TestDeconstructNamespace:
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
            _TestDeconstructNamespace.SimpleModel,
            {
                "name": "SimpleModel",
                "fields": {
                    "name": {
                        "max_length": 255,
                        "type": pw.CharField,
                        "column_name": "name",
                        "default_constraint": None,
                        "index": (False, False),
                    }
                },
                "meta": {"table_name": "simplemodel"},
            },
        ),
        (
            _TestDeconstructNamespace.ComplicatedModel,
            {
                "name": "ComplicatedModel",
                "fields": {
                    "name": {
                        "max_length": 5,
                        "type": pw.CharField,
                        "column_name": "name",
                        "default_constraint": None,
                        "index": (False, False),
                    },
                    "age": {
                        "type": pw.IntegerField,
                        "column_name": "age",
                        "default_constraint": None,
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
