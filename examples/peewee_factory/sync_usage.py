import peewee as pw
from playhouse.postgres_ext import PostgresqlExtDatabase

from miggy.ext.peewee_factory import PeeweeFactory

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"

db = PostgresqlExtDatabase(POSTGRES_DSN)


class Author(pw.Model):
    name = pw.CharField(max_length=20)

    class Meta:
        database = db


class Book(pw.Model):
    title = pw.CharField()
    author = pw.ForeignKeyField(Author, null=True)

    class Meta:
        database = db


class BookFactory(PeeweeFactory[Book]):
    __allow_none_optionals__ = False


def main() -> Book:
    db.drop_tables([Book, Author], safe=True)
    db.create_tables([Author, Book])
    BookFactory.build()  # unsaved instance
    book = BookFactory.create_sync()  # built and saved, FK relations included
    books = BookFactory.create_batch_sync(5)
    print(f"created: {book.id} {book.title} by {book.author.name}")
    print(f"batch created: {len(books)} books")
    db.drop_tables([Book, Author], safe=True)
    db.close()


if __name__ == "__main__":
    main()
