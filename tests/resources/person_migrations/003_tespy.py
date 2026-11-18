"""Peewee migrations -- 003_tespy.py.

A migration is a `Migration` class. `forward` and `backward` are lists of
operations from `miggy.operations` to apply forward and backward.
Set `atomic = True` to run the migration inside a single transaction.
"""

from miggy import operations


class Migration(operations.Migration):
    atomic = True

    forward = [
        operations.RenameField(
            model_name="tag",
            old_name="created_at",
            new_name="updated_at",
        ),
    ]

    backward = [
        operations.RenameField(
            model_name="tag",
            old_name="updated_at",
            new_name="created_at",
        ),
    ]
