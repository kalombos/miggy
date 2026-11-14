"""Peewee migrations -- 004_test_insert.py.

A migration is a `Migration` class. `forward` and `backward` are lists of
operations from `miggy.operations` to apply forward and backward.
Set `atomic = True` to run the migration inside a single transaction.
"""

from miggy import operations
from miggy.schema import SchemaMigrator
from miggy.state import State


def save_person(schema_migrator: SchemaMigrator, state: State) -> None:
    Person = state["person"]
    Person(
        first_name="First",
        last_name="Last",
        email="person@example.com",
    ).save()


def delete_person(schema_migrator: SchemaMigrator, state: State) -> None:
    Person = state["person"]
    Person.delete().where(Person.email == "person@example.com").execute()


class Migration(operations.Migration):
    atomic = True

    forward = [
        operations.RunPython(save_person),
    ]

    backward = [
        operations.RunPython(delete_person),
    ]
