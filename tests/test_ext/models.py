from enum import IntEnum, StrEnum

import peewee as pw
from playhouse.postgres_ext import DateTimeTZField

from miggy.ext import CharEnumField, IntEnumField
from tests.conftest import POSTGRES_DSN

db = pw.PostgresqlDatabase(POSTGRES_DSN)


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Author(pw.Model):
    class Meta:
        database = db

    name = pw.CharField()
    last_name = pw.CharField()
    age = pw.IntegerField()
    created_at = DateTimeTZField()
    status = CharEnumField(Status)


class Rating(IntEnum):
    LOW = 1
    MIDDLE = 2
    HIGH = 3


class Book(pw.Model):
    class Meta:
        database = db

    title = pw.CharField(max_length=10)
    author = pw.ForeignKeyField(Author)
    rating = pw.IntegerField()
    requests = pw.IntegerField(default=0)
    rating = IntEnumField(Rating)
    feedback = pw.CharField(null=True)
