from typing import Any

import peewee as pw
import pytest
from playhouse.postgres_ext import DateTimeTZField

from miggy.deconstructor import (
    Deconstructed,
    ForeignKeyFieldDeconstructor,
    ModelDeconstructor,
    deconstructor_factory,
    deep_deconstruct,
)
from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.types import ModelCls
from tests.helpers import Rating, Status, get_active_status, get_inactive_status


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
def test_deconstruct_type_modifiers(field: pw.Field, expected: type[pw.Field]) -> None:
    assert deconstructor_factory(field).deconstruct_type_modifiers() == expected


@pytest.mark.parametrize(
    ("field_name", "field", "expected"),
    [
        (
            "some_field_id",
            pw.ForeignKeyField(
                _M1, on_delete="CASCADE", on_update="RESTRICT", constraint_name="constraint_name", null=True
            ),
            {
                "model": "_m1",
                "constraint_name": "constraint_name",
                "on_delete": "CASCADE",
                "on_update": "RESTRICT",
                "null": True,
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1, column_name="some_field_id"),
            {
                "model": "_m1",
            },
        ),
        (
            "some_field_id",
            pw.ForeignKeyField(_M1, column_name="some_field_id"),
            {
                "model": "_m1",
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1, column_name="some_field"),
            {
                "model": "_m1",
                "column_name": "some_field",
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1),
            {
                "model": "_m1",
            },
        ),
        # test indexes
        (
            "some_field",
            pw.ForeignKeyField(_M1, index=False),
            {
                "model": "_m1",
                "index": False,
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1, unique=True, index=False),
            {
                "model": "_m1",
                "unique": True,
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1, unique=True),
            {
                "model": "_m1",
                "unique": True,
            },
        ),
        (
            "some_field",
            pw.ForeignKeyField(_M1, primary_key=True, index=False),
            {
                "model": "_m1",
                "primary_key": True,
            },
        ),
    ],
)
def test_foreignkey_field_deconstructor_deconstruct_params(
    field_name: str, field: pw.Field, expected: dict[str, Any]
) -> None:
    class MyTestModel(pw.Model):
        pass

    MyTestModel._meta.add_field(field_name, field)
    assert ForeignKeyFieldDeconstructor(field).deconstruct_params() == expected


class _TestDeconstructFkParamsNamespace:
    class M1(pw.Model):
        name = pw.CharField()


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        pytest.param(
            pw.ForeignKeyField(
                _TestDeconstructFkParamsNamespace.M1,
                on_delete="CASCADE",
                on_update="RESTRICT",
                constraint_name="constraint_name",
                null=True,
                field="name",
            ),
            {
                "model": "m1",
                "constraint_name": "constraint_name",
                "on_delete": "CASCADE",
                "on_update": "RESTRICT",
                "field": "name",
            },
            id="custom_values",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestDeconstructFkParamsNamespace.M1),
            {
                "model": "m1",
            },
            id="default_values",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestDeconstructFkParamsNamespace.M1, field="id"),
            {
                "model": "m1",
            },
            id="field_same_primary_key",
        ),
    ],
)
def test_foreignkey_field_deconstruct_fk_params(field: pw.Field, expected: dict[str, Any]) -> None:
    class MyTestModel(pw.Model):
        pass

    MyTestModel._meta.add_field("field_name", field)
    assert ForeignKeyFieldDeconstructor(field).deconstruct_fk_params() == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (
            pw.ForeignKeyField(_M1, null=True),
            {
                "model": "_m1",
                "null": True,
            },
        ),
        # test column_name
        (pw.IntegerField(column_name="some_name"), {"column_name": "some_name"}),
        # test indexes
        (
            pw.CharField(max_length=55, index=True, unique=True),
            {"unique": True, "max_length": 55},
        ),
        (pw.IntegerField(unique=True), {"unique": True}),
        (pw.IntegerField(index=True), {"index": True}),
        (pw.IntegerField(index=True, primary_key=True), {"primary_key": True}),
        # test autofield
        (pw.AutoField(index=True, unique=True, primary_key=True), {}),
        # test default callable
        (pw.CharField(default=get_active_status), {"default": get_active_status}),
    ],
)
def test_field_deconstruct_params(field: pw.Field, expected: dict[str, Any]) -> None:
    class MyTestModel(pw.Model):
        some_field = field

    assert deconstructor_factory(MyTestModel.some_field).deconstruct_params() == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (
            pw.IntegerField(column_name="some_name"),
            Deconstructed("peewee.IntegerField", {"column_name": "some_name"}),
        ),
        (DateTimeTZField(), Deconstructed("playhouse.postgres_ext.DateTimeTZField", {})),
        (CharEnumField(Status, max_length=50), Deconstructed("peewee.CharField", {"max_length": 50})),
        (IntEnumField(Rating), Deconstructed("peewee.SmallIntegerField", {})),
    ],
)
def test_field_deconstruct(field: pw.Field, expected: dict[str, Any]) -> None:
    class MyTestModel(pw.Model):
        some_field = field

    assert deconstructor_factory(MyTestModel.some_field).deconstruct() == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        pytest.param(
            pw.ForeignKeyField(_M1, null=True),
            {
                "model": "_m1",
                "null": True,
            },
            id="default_rel_field",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, field="name"),
            {
                "model": "_m1",
                "field": "name",
            },
            id="custom_rel_field",
        ),
        pytest.param(pw.IntegerField(), {}, id="default_column_name"),
        pytest.param(
            pw.IntegerField(column_name="some_name"),
            {"column_name": "some_name"},
            id="custom_column_name",
        ),
    ],
)
def test_deconstruct_params_unbound(field: pw.Field, expected: dict[str, Any]) -> None:
    assert deconstructor_factory(field).deconstruct_params() == expected


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
        # test default callable equality
        pytest.param(pw.CharField(default=get_active_status), pw.CharField(default=get_inactive_status), True),
        pytest.param(pw.CharField(default=get_active_status), pw.CharField(default=get_active_status), False),
    ],
)
def test_deep_deconstruct_not_equal(f1: pw.Field, f2: pw.Field, expected: bool) -> None:
    class TestModel1(pw.Model):
        some_field = f1

    class TestModel2(pw.Model):
        some_field = f2

    not_equal = deep_deconstruct(TestModel1.some_field) != deep_deconstruct(TestModel2.some_field)
    assert not_equal is expected


@pytest.mark.parametrize(
    ("f", "expected"),
    [
        (
            pw.CharField(max_length=50),
            Deconstructed("peewee.CharField", {"max_length": 50}),
        ),
        (
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 'words'")]),
            Deconstructed(
                "peewee.IntegerField",
                {
                    "constraints": [{"value": "'words'"}],
                },
            ),
        ),
    ],
)
def test_deep_deconstruct(f: pw.Field, expected: Deconstructed) -> None:
    class TestModel(pw.Model):
        some_field = f

    assert deep_deconstruct(TestModel.some_field) == expected


class _TestModelDeconstructNamespace:
    class SimpleModel(pw.Model):
        name = pw.CharField()

    class ComplicatedModel(pw.Model):
        name = pw.CharField(max_length=5)
        age = pw.IntegerField()

        class Meta:
            schema = "new_schema"
            primary_key = pw.CompositeKey("name", "age")
            table_name = "custom_name"


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (
            _TestModelDeconstructNamespace.SimpleModel,
            {
                "name": "SimpleModel",
                "fields": {"name": {}},
                "meta": {},
            },
        ),
        (
            _TestModelDeconstructNamespace.ComplicatedModel,
            {
                "name": "ComplicatedModel",
                "fields": {
                    "name": {
                        "max_length": 5,
                    },
                    "age": {},
                },
                "meta": {"table_name": "custom_name", "schema": "new_schema", "primary_key": ("name", "age")},
            },
        ),
    ],
)
def test_model_deconstructor__deconstruct(model: ModelCls, expected: dict[str, Any]) -> None:
    deconstructed = ModelDeconstructor(model).deconstruct()
    deconstructed["fields"] = {
        n: deconstructor_factory(f).deconstruct_params() for n, f in deconstructed["fields"].items()
    }
    if "primary_key" in deconstructed["meta"]:
        deconstructed["meta"]["primary_key"] = deconstructed["meta"]["primary_key"].field_names
    assert deconstructed == expected
