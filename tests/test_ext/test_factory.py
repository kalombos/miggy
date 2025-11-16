import pytest

from miggy.ext import model_factory
from miggy.ext.factory import FieldNotFound

from .models import Author, Book


def test_foreign_field_is_created():
    book = model_factory(Book)
    Author.get(id=book.author)


def test_default_field_is_not_generated():
    book = model_factory(Book)
    assert book.requests == 0


def test_error_for_unknown_field():
    with pytest.raises(FieldNotFound):
        model_factory(Book, unknown_field="value")
