"""Peewee migrations -- 001_test.py.

A migration is a `Migration` class. `forward` and `backward` are lists of
operations from `miggy.operations` to apply forward and backward.
Set `atomic = True` to run the migration inside a single transaction.
"""

import datetime as dt

import peewee as pw

from miggy import operations


class Migration(operations.Migration):
    atomic = True

    forward = [
        operations.CreateModel(
            name="Tag",
            fields={
                "tag": pw.CharField(),
            },
            meta={},
        ),
        operations.CreateModel(
            name="Person",
            fields={
                "first_name": pw.CharField(),
                "last_name": pw.CharField(index=True),
                "dob": pw.DateField(null=True),
                "birthday": pw.DateField(default=dt.datetime.now),
                "email": pw.CharField(index=True, unique=True),
            },
            meta={},
        ),
    ]

    backward = [
        operations.RemoveModel(
            "Person",
        ),
        operations.RemoveModel(
            "Tag",
        ),
    ]
