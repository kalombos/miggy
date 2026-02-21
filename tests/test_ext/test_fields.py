
import pytest

from miggy.ext import model_factory

from .models import Author, Book, Rating, Status, db


def test_intenumfield() -> None:
    model_factory(Book, rating=Rating.HIGH)

    book = Book.select().where(Book.rating == Rating.HIGH).execute()[0]
    assert book.rating == Rating.HIGH


def test_intenumfield__raw() -> None:
    model_factory(Book, rating=3)

    book = Book.select().where(Book.rating == 3).execute()[0]
    assert book.rating == Rating.HIGH


def test_intenumfield__error_on_create() -> None:
    with pytest.raises(ValueError):
        model_factory(Book, rating=4)


def test_intenumfield__error_on_get() -> None:
    author = model_factory(Author)
    db.execute_sql(
        """
        INSERT INTO "book" ("title", "author_id", "requests", "rating") VALUES ('title1', %s, 0, 5)
    """, params=[author.id])

    with pytest.raises(ValueError):
        Book.get()

def test_charenumfield() -> None:
    model_factory(Author, status=Status.ACTIVE)

    author = Author.select().where(Author.status == Status.ACTIVE).execute()[0]
    assert author.status == Status.ACTIVE


def test_charenumfield__raw() -> None:
    model_factory(Author, status="active")

    author = Author.select().where(Author.status == "active").execute()[0]
    assert author.status == Status.ACTIVE


def test_charenumfield__error_on_create() -> None:
    with pytest.raises(ValueError):
        model_factory(Author, status="some")


def test_charenumfield__error_on_get() -> None:
    db.execute_sql(
        """
        INSERT INTO "author" ("name", "last_name", "age", "created_at", "status") 
        VALUES ('name1', 'last_name1', 1, '2026-02-21T10:36:21.913527+00:00'::timestamptz, 'unknown')
    """
    )

    with pytest.raises(ValueError):
        Author.get()