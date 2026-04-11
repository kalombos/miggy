import peewee as pw
import pytest

from miggy.deconstructor import FieldDeconstructor
from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
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
def test_field_comparer_get_type_params(field: pw.Field, expected: type[pw.Field]) -> None:
    assert FieldDeconstructor(field).get_type_params() == expected


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
def test_field_comparer_get_type(field: pw.Field, expected: type[pw.Field]) -> None:
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
    assert FieldDeconstructor.not_equal(f1, f2) is expected
