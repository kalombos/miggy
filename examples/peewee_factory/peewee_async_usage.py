import asyncio
from typing import TypeVar

import peewee as pw
import peewee_async
from polyfactory.persistence import AsyncPersistenceProtocol

from miggy.ext.peewee_factory import PeeweeAsyncPersistence as _PeeweeAsyncPersistence
from miggy.ext.peewee_factory import PeeweeFactory as _PeeweeFactory

T = TypeVar("T", bound=pw.Model)

# A peewee-async database manages an async connection pool.
db = peewee_async.PostgresqlDatabase(
    "postgres",
    user="postgres",
    password="postgres",
    host="localhost",
    port=5432,
)


class Author(peewee_async.AioModel):
    name = pw.CharField(max_length=20)

    class Meta:
        database = db


class Book(peewee_async.AioModel):
    title = pw.CharField()
    author = pw.ForeignKeyField(Author, null=True)

    class Meta:
        database = db


# The default async persistence is based on playhouse.pwasyncio, which does not
# work with peewee-async models. Override it to save instances with AioModel.aio_save.
class PeeweeAsyncPersistence(_PeeweeAsyncPersistence):
    async def _save(self, m: pw.Model) -> None:
        await m.aio_save(force_insert=True)


class PeeweeFactory(_PeeweeFactory[T]):
    # Mark the class as a base factory, so it can be subclassed without __model__.
    __is_base_factory__ = True

    @classmethod
    def _get_async_persistence(cls) -> AsyncPersistenceProtocol[T]:
        return PeeweeAsyncPersistence()


class BookFactory(PeeweeFactory[Book]):
    __allow_none_optionals__ = False


async def main() -> Book:
    await db.aio_drop_tables([Book, Author], safe=True)
    await db.aio_create_tables([Author, Book])
    book = await BookFactory.create_async()
    print(f"created: {book.id} {book.title} by {book.author.name}")

    await db.aio_drop_tables([Book, Author], safe=True)
    await db.aio_close()


if __name__ == "__main__":
    asyncio.run(main())
