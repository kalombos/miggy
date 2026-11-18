import datetime as dt

import peewee as pw
import pytest
from playhouse import pwasyncio
from polyfactory.exceptions import ParameterException

from miggy.ext import CharEnumField
from miggy.ext.polyfactory import PeeweeFactory
from miggy.ext.utils import StrEnum

db = pw.SqliteDatabase(":memory:")


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PFPublisher(pw.Model):
    class Meta:
        database = db

    name = pw.CharField()


class PFAuthor(pw.Model):
    class Meta:
        database = db

    name = pw.CharField(max_length=20)
    age = pw.IntegerField(null=True)
    status = CharEnumField(Status)
    created_at = pw.DateTimeField(default=dt.datetime.utcnow)
    publisher = pw.ForeignKeyField(PFPublisher, null=True)


class PFBook(pw.Model):
    class Meta:
        database = db

    title = pw.CharField()
    author = pw.ForeignKeyField(PFAuthor, null=True)
    rating = pw.DecimalField(max_digits=5, decimal_places=2)


class PFAuthorFactory(PeeweeFactory[PFAuthor]):
    __allow_none_optionals__ = False


class PFPublisherFactory(PeeweeFactory[PFPublisher]):
    __allow_none_optionals__ = False


class PFBookFactory(PeeweeFactory[PFBook]):
    __allow_none_optionals__ = False


@pytest.fixture(autouse=True)
def sync_db():
    db.create_tables([PFPublisher, PFAuthor, PFBook])
    yield
    PFBook.delete().execute()
    PFAuthor.delete().execute()
    PFPublisher.delete().execute()


def test_build_creates_unsaved_instance() -> None:
    book = PFBookFactory.build()

    assert isinstance(book, PFBook)
    assert book.id is None
    assert book.title
    assert isinstance(book.author, PFAuthor)
    assert book.author.id is None


def test_build_respects_char_max_length() -> None:
    for _ in range(10):
        author = PFAuthorFactory.build()
        assert len(author.name) <= 20


def test_build_fills_enum_field() -> None:
    author = PFAuthorFactory.build()
    assert author.status in (Status.ACTIVE, Status.INACTIVE)


def test_create_sync_saves_model_and_relations() -> None:
    book = PFBookFactory.create_sync()

    assert isinstance(book, PFBook)
    assert book.id is not None
    assert book.author.id is not None
    # the unsaved author and its unsaved publisher are saved together
    assert book.author.publisher.id is not None
    assert PFAuthor.get(id=book.author.id).name == book.author.name
    assert PFPublisher.get(id=book.author.publisher.id).name == book.author.publisher.name


def test_create_sync_uses_default_field_value() -> None:
    class PFAuthorDefaultsFactory(PeeweeFactory[PFAuthor]):
        __use_defaults__ = True
        __allow_none_optionals__ = False

    before = dt.datetime.utcnow()  # noqa: DTZ003
    author = PFAuthorDefaultsFactory.create_sync()
    assert before < author.created_at


def test_create_sync_overrides_kwargs() -> None:
    book = PFBookFactory.create_sync(title="custom")
    assert book.title == "custom"


def test_batch_creates_unsaved_instances() -> None:
    books = PFBookFactory.batch(3)

    assert len(books) == 3
    assert all(isinstance(book, PFBook) for book in books)


# --- async ---

async_db = pwasyncio.AsyncSqliteDatabase(":memory:")


class AsyncAuthor(pwasyncio.AsyncModel):
    class Meta:
        database = async_db

    name = pw.CharField()


class AsyncBook(pwasyncio.AsyncModel):
    class Meta:
        database = async_db

    title = pw.CharField()
    author = pw.ForeignKeyField(AsyncAuthor, null=True)


class AsyncBookFactory(PeeweeFactory[AsyncBook]):
    __allow_none_optionals__ = False


@pytest.mark.asyncio
async def test_create_async_saves_model_and_relations() -> None:
    async with async_db:
        await async_db.acreate_tables([AsyncAuthor, AsyncBook])

        book = await AsyncBookFactory.create_async()

        assert book.id is not None
        assert book.author.id is not None
        author = await AsyncAuthor.aget(id=book.author.id)
        assert author.name == book.author.name
        await async_db.adrop_tables([AsyncAuthor, AsyncBook])
    await async_db.close_pool()


@pytest.mark.asyncio
async def test_create_async_requires_async_model() -> None:
    with pytest.raises(ParameterException, match="not an AsyncModel"):
        await PFBookFactory.create_async()
