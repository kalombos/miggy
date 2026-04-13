import peewee as pw
import pytest

from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.serializer import FieldSerializer, serialize_value
from tests.helpers import Rating, Status


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # TODO add tests for other serializers
        (5, "5"),
        ("5", "'5'"),
        ("O'neal", '"O\'neal"'),
        (Status.ACTIVE, "'active'"),
        (Rating.LOW, "1"),
    ],
)
def test_serialize_value(value: int | str, expected: str) -> None:
    assert serialize_value(value) == expected


def test_field_serializer_to_code() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])
        status = CharEnumField(Status, null=True, max_length=100, default=Status.ACTIVE)
        rating = IntEnumField(Rating)

    assert FieldSerializer(SomeModel.name).serialize() == (
        """name=pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
    assert FieldSerializer(SomeModel.status).serialize() == (
        """status=pw.CharField(default='active', max_length=100, null=True)"""
    )
    assert FieldSerializer(SomeModel.rating).serialize() == ("""rating=pw.SmallIntegerField()""")
