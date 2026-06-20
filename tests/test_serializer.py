import peewee as pw
import pytest
from playhouse.postgres_ext import DateTimeTZField

from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.serializer import FieldSerializer, serializer_factory
from tests.helpers import Rating, Status


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, "5"),
        ("5", "'5'"),
        ("O'neal", '"O\'neal"'),
        (Status.ACTIVE, "'active'"),
        (Rating.LOW, "1"),
        (pw.CompositeKey("name", "age"), "pw.CompositeKey('name', 'age')"),
        (pw.SQL("where name='%s'", params=["John"]), """pw.SQL("where name='%s'", ['John'])"""),
        (pw.SQL("DEFAULT 5"), "pw.SQL('DEFAULT 5')"),
        (pw.SQL("where name='%s'", params=("John",)), """pw.SQL("where name='%s'", ('John',))"""),
    ],
)
def test_serialize_value(value: int | str, expected: str) -> None:
    assert serializer_factory(value).serialize().code == expected


def test_field_serializer_serialize() -> None:
    class LinkModel(pw.Model):
        some_field = pw.CharField()

    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])
        status = CharEnumField(Status, null=True, max_length=100, default=Status.ACTIVE)
        rating = IntEnumField(Rating)
        updated_at = DateTimeTZField()
        link_model = pw.ForeignKeyField(LinkModel)
        index_field = pw.IntegerField(index=True, unique=True)

    assert FieldSerializer(SomeModel.name).serialize().code == (
        """pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
    assert FieldSerializer(SomeModel.status).serialize().code == (
        """pw.CharField(default='active', max_length=100, null=True)"""
    )
    assert FieldSerializer(SomeModel.updated_at).serialize().code == ("""pw_pext.DateTimeTZField()""")
    assert FieldSerializer(SomeModel.rating).serialize().code == ("""pw.SmallIntegerField()""")
    assert FieldSerializer(SomeModel.link_model).serialize().code == ("""pw.ForeignKeyField(model='linkmodel')""")
    assert FieldSerializer(SomeModel.index_field).serialize().code == ("""pw.IntegerField(unique=True)""")
