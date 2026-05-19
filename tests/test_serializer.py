import peewee as pw
import pytest
from playhouse.postgres_ext import DateTimeTZField

from miggy.ext import IntEnumField
from miggy.ext.fields import CharEnumField
from miggy.serializer import FieldSerializer, serialize_field, serialize_value
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
    assert serialize_value(value) == expected


def test_field_serializer_serialize() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])
        status = CharEnumField(Status, null=True, max_length=100, default=Status.ACTIVE)
        updated_at = DateTimeTZField()

    assert FieldSerializer(SomeModel.name).serialize() == (
        """pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
    assert FieldSerializer(SomeModel.status).serialize() == (
        """pw.CharField(default='active', max_length=100, null=True)"""
    )
    assert FieldSerializer(SomeModel.updated_at).serialize() == ("""pw_pext.DateTimeTZField()""")


def test_serialize_field() -> None:
    class LinkModel(pw.Model):
        some_field = pw.CharField()

    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])
        status = CharEnumField(Status, null=True, max_length=100, default=Status.ACTIVE)
        rating = IntEnumField(Rating)
        link_model = pw.ForeignKeyField(LinkModel)
        index_field = pw.IntegerField(index=True, unique=True)

    assert serialize_field(SomeModel.name) == (
        """name=pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
    assert serialize_field(SomeModel.status, add_space=True) == (
        """status = pw.CharField(default='active', max_length=100, null=True)"""
    )
    assert serialize_field(SomeModel.rating) == ("""rating=pw.SmallIntegerField()""")
    assert serialize_field(SomeModel.link_model) == (
        """link_model=pw.ForeignKeyField(model=migrator.state['linkmodel'])"""
    )
    assert serialize_field(SomeModel.index_field) == ("""index_field=pw.IntegerField(unique=True)""")
