import peewee as pw
import pytest

from miggy.operations import (
    AddFields,
    AddIndex,
    ChangeFields,
    CreateModel,
    DropIndex,
    MigrateOperation,
    RemoveFields,
    RemoveModel,
    RenameTable,
)
from miggy.writer import OperationWriter
from tests.helpers import compare_dedent


class Car(pw.Model):
    name = pw.CharField()


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
                    'email': pw.CharField(null=True),
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
        pytest.param(
            AddIndex(
                "user",
                "field1",
                "field2",
                name="user_index",
                where=pw.SQL("field1 = 'bob'"),
                safe=True,
                concurrently=True,
            ),
            """
            migrator.add_index(
                'user',
                'field1',
                'field2',
                name='user_index',
                where=pw.SQL("field1 = 'bob'"),
                safe=True,
                concurrently=True,
            )
            """,
            id="AddIndex",
        ),
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
        pytest.param(
            AddFields(
                "user",
                name=pw.CharField(max_length=100, constraints=[pw.SQL("DEFAULT 'Max'")]),
                email=pw.CharField(max_length=255, null=True),
                car=pw.ForeignKeyField(Car, field="name"),
            ),
            """
            migrator.add_fields(
                'user',
                name=pw.CharField(constraints=[pw.SQL("DEFAULT 'Max'")], max_length=100),
                email=pw.CharField(null=True),
                car=pw.ForeignKeyField(field='name', model='car'),
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
                email=pw.CharField(null=True),
            )
            """,
            id="ChangeFields",
        ),
        pytest.param(
            RemoveFields("user", "field1", "field2"),
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
