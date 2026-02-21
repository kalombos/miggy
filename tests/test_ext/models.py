from enum import IntEnum

import peewee as pw
from playhouse.postgres_ext import DateTimeTZField

from miggy.ext import CharEnumField, IntEnumField
from miggy.ext.utils import StrEnum
from tests.conftest import POSTGRES_DSN

db = pw.PostgresqlDatabase(POSTGRES_DSN)


class Status(StrEnum):
    active = "active"
    inactive = "inactive"


class Author(pw.Model):
    class Meta:
        database = db

    name = pw.CharField()
    last_name = pw.CharField()
    age = pw.IntegerField()
    created_at = DateTimeTZField()
    status = CharEnumField(Status)


class Rating(IntEnum):
    low = 1
    middle = 2
    high = 3


class Book(pw.Model):
    class Meta:
        database = db

    title = pw.CharField()
    author = pw.ForeignKeyField(Author)
    rating = pw.IntegerField()
    requests = pw.IntegerField(default=0)
    rating = IntEnumField(Rating)
