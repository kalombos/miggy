import peewee as pw
import pytest

from miggy.operations import (
    AddField,
    AddIndex,
    AddPrimaryKeyConstraint,
    AlterField,
    CreateModel,
    DropIndex,
    MigrateOperation,
    RemoveField,
    RemoveModel,
    RemovePrimaryKeyConstraint,
    RenameTable,
)
from miggy.utils import CheckMeta
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
                    "constraints": [CheckMeta("some_name", "name != 'bob'")],
                },
            ),
            """
            operations.CreateModel(
                'user',
                {
                    'name': pw.CharField(max_length=100),
                    'email': pw.CharField(null=True),
                },
                meta={
                    'table_name': 'some_table',
                    'schema': 'some_schema',
                    'primary_key': pw.CompositeKey('name', 'email'),
                    'constraints': [pw.Check("name != 'bob'", name='some_name')],
                },
            ),
            """,
            id="CreateModel",
        ),
        pytest.param(
            RemoveModel("user"),
            """
            operations.RemoveModel(
                'user',
            ),
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
            operations.AddIndex(
                'user',
                'field1',
                'field2',
                name='user_index',
                where=pw.SQL("field1 = 'bob'"),
                safe=True,
                concurrently=True,
            ),
            """,
            id="AddIndex",
        ),
        pytest.param(
            DropIndex("user", name="user_index"),
            """
            operations.DropIndex(
                'user',
                name='user_index',
            ),
            """,
            id="DropIndex",
        ),
        pytest.param(
            RenameTable("user", "usertable"),
            """
            operations.RenameTable(
                'user',
                'usertable',
            ),
            """,
            id="RenameTable",
        ),
        pytest.param(
            AddField(
                "user",
                name="name",
                field=pw.CharField(max_length=100, constraints=[pw.SQL("DEFAULT 'Max'")]),
            ),
            """
            operations.AddField(
                'user',
                name='name',
                field=pw.CharField(constraints=[pw.SQL("DEFAULT 'Max'")], max_length=100),
            ),
            """,
            id="AddField",
        ),
        pytest.param(
            AlterField(
                "user",
                name="email",
                field=pw.CharField(max_length=255, null=True),
            ),
            """
            operations.AlterField(
                'user',
                name='email',
                field=pw.CharField(null=True),
            ),
            """,
            id="AlterField",
        ),
        pytest.param(
            RemoveField("user", "field1"),
            """
            operations.RemoveField(
                'user',
                'field1',
            ),
            """,
            id="RemoveField",
        ),
        pytest.param(
            AddPrimaryKeyConstraint("user", "name", "email"),
            """
            operations.AddPrimaryKeyConstraint(
                'user',
                'name',
                'email',
            ),
            """,
            id="AddPrimaryKeyConstraint",
        ),
        pytest.param(
            RemovePrimaryKeyConstraint("user"),
            """
            operations.RemovePrimaryKeyConstraint(
                'user',
            ),
            """,
            id="RemovePrimaryKeyConstraint",
        ),
    ],
)
def test_serialize(operation: MigrateOperation, expected: str) -> None:
    compare_dedent(OperationWriter(operation).serialize(), expected)
