from textwrap import dedent

import peewee as pw
import pytest

from miggy.operations import (
    AddFields,
    ChangeFields,
    CreateModel,
    DropIndex,
    MigrateOperation,
    RemoveFields,
    RemoveModel,
    RenameTable,
)
from miggy.writer import OperationWriter


def compare_dedent(s1: str, s2: str) -> None:
    assert dedent(s1).strip() == dedent(s2).strip()


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        pytest.param(
            CreateModel(
                "user",
                {
                    "name": pw.CharField(max_length=100),
                    "email": pw.CharField(max_length=255, null=True),
                },
                meta={
                    "table_name": "some_table",
                    "schema": "some_schema",
                    "primary_key": pw.CompositeKey("name", "email"),
                },
            ),
            """
            migrator.create_model(
                'user',
                {
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
            id="CreateModel",
        ),
        pytest.param(
            RemoveModel("user"),
            """
            migrator.remove_model(
                'user',
            )
            """,
            id="RemoveModel",
        ),
        # TODO
        # pytest.param(
        #     AddIndex("user", "field1", "field2", name="user_index", where=pw.SQL("field1 = 'bob'")),
        #     """
        #     migrator.add_index(
        #         'user',
        #         'field1',
        #         'field2',
        #         name='user_index',
        #     )
        #     """,
        #     id="AddIndex",
        # ),
        pytest.param(
            DropIndex("user", name="user_index"),
            """
            migrator.drop_index(
                'user',
                name='user_index',
            )
            """,
            id="DropIndex",
        ),
        pytest.param(
            RenameTable("user", "usertable"),
            """
            migrator.rename_table(
                'user',
                'usertable',
            )
            """,
            id="RenameTable",
        ),
        # TODO add fk
        pytest.param(
            AddFields(
                "user",
                name=pw.CharField(max_length=100),
                email=pw.CharField(max_length=255, null=True),
            ),
            """
            migrator.add_fields(
                'user',
                name=pw.CharField(max_length=100),
                email=pw.CharField(max_length=255, null=True),
            )
            """,
            id="AddFields",
        ),
        pytest.param(
            ChangeFields(
                "user",
                name=pw.CharField(max_length=100),
                email=pw.CharField(max_length=255, null=True),
            ),
            """
            migrator.change_fields(
                'user',
                name=pw.CharField(max_length=100),
                email=pw.CharField(max_length=255, null=True),
            )
            """,
            id="ChangeFields",
        ),
        pytest.param(
            RemoveFields(
                "user",
                "field1",
                "field2"
            ),
            """
            migrator.remove_fields(
                'user',
                'field1',
                'field2',
            )
            """,
            id="RemoveFields",
        ),
    ],
)
def test_serialize(operation: MigrateOperation, expected: str) -> None:
    compare_dedent(OperationWriter(operation).serialize(), expected)
