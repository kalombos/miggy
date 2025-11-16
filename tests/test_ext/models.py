import peewee as pw

from tests.conftest import POSTGRES_DSN

db = pw.PostgresqlDatabase(POSTGRES_DSN)


class Author(pw.Model):
    class Meta:
        database = db

    name = pw.CharField()
    last_name = pw.CharField()
    age = pw.IntegerField()


class Book(pw.Model):
    class Meta:
        database = db

    title = pw.CharField()
    author = pw.ForeignKeyField(Author)
    rating = pw.IntegerField()
    requests = pw.IntegerField(default=0)
