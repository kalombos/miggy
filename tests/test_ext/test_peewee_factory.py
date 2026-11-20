import datetime as dt
from collections.abc import AsyncGenerator

import peewee as pw
import pytest
import pytest_asyncio

from tests.conftest import POSTGRES_DSN
from tests.test_ext.utils import list_models

pytest.importorskip("peewee", minversion="4.0")


from playhouse import pwasyncio

from miggy.ext.peewee_factory import PeeweeFactory
from miggy.utils import EnumField, IntEnumField
from tests.helpers import Rating, Status, skip_if_no_enum

from .models import Author, Book, db


class AuthorFactory(PeeweeFactory[Author]):
    pass


class BookFactory(PeeweeFactory[Book]):
    pass


@pytest_asyncio.fixture
async def async_mode() -> AsyncGenerator[None]:
    async_db = pwasyncio.AsyncPostgresqlDatabase(POSTGRES_DSN)
    for m in list_models():
        m._meta.database = async_db
    yield
    await async_db.aclose()
    await async_db.close_pool()
    for m in list_models():
        m._meta.database = db


def test_build() -> None:
    book = BookFactory.build()

    assert isinstance(book, Book)
    assert book.id is None
    assert isinstance(book.title, str)

    author = book.author
    assert isinstance(author, Author)
    assert author.id is None
    assert isinstance(author.created_at, dt.datetime)


def test_build__options() -> None:
    class TestBookFactory(PeeweeFactory[Book]):
        __use_defaults__ = True
        __allow_none_optionals__ = False

    book = TestBookFactory.build()
    assert book.requests == 0
    assert book.feedback is not None


@skip_if_no_enum
def test_enum_field() -> None:
    class SomeModel(pw.Model):
        status = EnumField(Status, max_length=100, null=True)
        rating = IntEnumField(Rating)

    class SomeModelFactory(PeeweeFactory[SomeModel]):
        __allow_none_optionals__ = False

    some_model = SomeModelFactory.build()
    assert isinstance(some_model.status, Status)
    assert isinstance(some_model.rating, Rating)


def test_create_sync() -> None:
    book = BookFactory.create_sync()

    assert isinstance(book, Book)
    assert book.id is not None
    assert book.author.id is not None
    assert Author.get(id=book.author.id).name == book.author.name
    assert Book.get(id=book.id).title == book.title


def test_create_sync_custom_fields() -> None:
    book = BookFactory.create_sync(title="custom")
    assert book.title == "custom"


@pytest.mark.asyncio
async def test_create_async(async_mode: None) -> None:
    book = await BookFactory.create_async()

    assert isinstance(book, Book)
    assert book.id is not None
    assert book.author.id is not None
    # assert await Author.aget(id=book.author.id).name == book.author.name
    # assert await Book.get(id=book.id).title == book.title
