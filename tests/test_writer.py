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
            AddField(
                "user",
                name="name",
                field=pw.CharField(max_length=100, constraints=[pw.SQL("DEFAULT 'Max'")]),
            ),
            """
            migrator.add_field(
                'user',
                name='name',
                field=pw.CharField(constraints=[pw.SQL("DEFAULT 'Max'")], max_length=100),
            )
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
            migrator.alter_field(
                'user',
                name='email',
                field=pw.CharField(null=True),
            )
            """,
            id="AlterField",
        ),
        pytest.param(
            RemoveField("user", "field1"),
            """
            migrator.remove_field(
                'user',
                'field1',
            )
            """,
            id="RemoveField",
        ),
        pytest.param(
            AddPrimaryKeyConstraint("user", "name", "email"),
            """
            migrator.add_primary_key_constraint(
                'user',
                'name',
                'email',
            )
            """,
            id="AddPrimaryKeyConstraint",
        ),
        pytest.param(
            RemovePrimaryKeyConstraint("user"),
            """
            migrator.remove_primary_key_constraint(
                'user',
            )
            """,
            id="RemovePrimaryKeyConstraint",
        ),
    ],
)
def test_serialize(operation: MigrateOperation, expected: str) -> None:
    compare_dedent(OperationWriter(operation).serialize(), expected)
