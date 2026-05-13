import peewee as pw

from miggy.operations import CreateModel
from miggy.writer import OperationWriter


def test_serialize() -> None:
    operation = CreateModel(
        "user",
        fields={
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
        meta={},
    )
    print()
    print(OperationWriter(operation).serialize())
