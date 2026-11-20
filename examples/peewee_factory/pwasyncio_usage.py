import asyncio

import peewee as pw
from playhouse import pwasyncio

from miggy.ext.peewee_factory import PeeweeFactory

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


async_db = pwasyncio.AsyncPostgresqlDatabase(POSTGRES_DSN)


class AsyncAuthor(pw.Model):
    name = pw.CharField(max_length=20)

    class Meta:
        database = async_db


class AsyncBook(pw.Model):
    title = pw.CharField()
    author = pw.ForeignKeyField(AsyncAuthor, null=True)

    class Meta:
        database = async_db


class AsyncBookFactory(PeeweeFactory[AsyncBook]):
    __allow_none_optionals__ = False


async def main() -> AsyncBook:
    await async_db.adrop_tables([AsyncBook, AsyncAuthor], safe=True)
    await async_db.acreate_tables([AsyncAuthor, AsyncBook])
    book = await AsyncBookFactory.create_async()
    print(f"created: {book.id} {book.title} by {book.author.name}")
    await async_db.adrop_tables([AsyncBook, AsyncAuthor], safe=True)
    await async_db.aclose()
    await async_db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
