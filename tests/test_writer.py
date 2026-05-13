

import peewee as pw

from miggy.operations import CreateModel
from miggy.writer import OperationWriter


def test_serialize() -> None:
    operation = CreateModel(
        "User",
        {
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
        {},
    )
    print()
    print(OperationWriter(operation).serialize())