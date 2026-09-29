import datetime as dt

import peewee as pw
import pytest

from miggy.ext import model_factory
from miggy.ext.factory import FieldNotFound
from miggy.utils import EnumField, IntEnumField
from tests.helpers import skip_if_no_enum

from .models import Author, Book, Rating, Status, db


def test_foreign_field_is_created() -> None:
    book = model_factory(Book)
    Author.get(id=book.author)


def test_default_field_is_not_generated() -> None:
    book = model_factory(Book)
    assert book.requests == 0


def test_dt_tz_field() -> None:
    _t = dt.datetime.now(tz=dt.timezone.utc)
    author = model_factory(Author)

    assert author.created_at > _t


def test_error_for_unknown_field() -> None:
    with pytest.raises(FieldNotFound):
        model_factory(Book, unknown_field="value")


@skip_if_no_enum
def test_enum_fields() -> None:
    class EnumModel(pw.Model):
        class Meta:
            database = db

        title = pw.CharField()
        status = EnumField(Status)
        rating = IntEnumField(Rating)

    EnumModel.create_table()

    book = model_factory(EnumModel)
    assert book.status == Status.ACTIVE
    assert book.rating == Rating.LOW

    EnumModel.drop_table()
