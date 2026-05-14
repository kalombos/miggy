from textwrap import dedent

import peewee as pw

from miggy.operations import CreateModel
from miggy.writer import OperationWriter


def compare_dedent(s1: str, s2: str) -> bool:
    assert dedent(s1).strip() == dedent(s2).strip()


def test_serialize() -> None:
    operation = CreateModel(
        "user",
        fields={
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
        meta={"table_name": "some_table", "schema": "some_schema", "primary_key": pw.CompositeKey("name", "email")},
    )

    compare_dedent(
        OperationWriter(operation).serialize(),
        """
        migrator.create_model(
            'user',
            fields={
                'name': pw.CharField(max_length=100),
                'email': pw.CharField(max_length=255, null=True),
            },
            meta={
                'table_name': 'some_table',
                'schema': 'some_schema',
                'primary_key': pw.CompositeKey('name', 'email'),
            },
        )
        """,
    )
