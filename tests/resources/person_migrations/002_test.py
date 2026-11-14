"""Peewee migrations -- 002_test.py.

A migration is a `Migration` class. `forward` and `backward` are lists of
operations from `miggy.operations` to apply forward and backward.
Set `atomic = True` to run the migration inside a single transaction.
"""

import peewee as pw

from miggy import operations


class Migration(operations.Migration):
    atomic = True

    forward = [
        operations.AddField(
            model_name="tag",
            name="created_at",
            field=pw.DateTimeField(null=True),
        ),
    ]

    backward = [
        operations.RemoveField(
            model_name="tag",
            name="created_at",
        ),
    ]
