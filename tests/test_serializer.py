import peewee as pw
import pytest

from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.serializer import FieldSerializer, serialize_value
from tests.helpers import Rating, Status


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, "5"),
        ("5", "'5'"),
        ("O'neal", '"O\'neal"'),
        (Status.ACTIVE, "'active'"),
        (Rating.LOW, "1"),
    ],
)
def test_base_serializer(value: int | str, expected: str) -> None:
    assert serialize_value(value) == expected


def test_field_serializer_to_code() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])
        status = CharEnumField(Status, null=True, max_length=100)
        rating = IntEnumField(Rating)

    assert FieldSerializer.to_code(SomeModel.name) == (
        """name = pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
    assert FieldSerializer.to_code(SomeModel.status) == ("""status = pw.CharField(max_length=100, null=True)""")
    assert FieldSerializer.to_code(SomeModel.rating) == ("""rating = pw.SmallIntegerField()""")
