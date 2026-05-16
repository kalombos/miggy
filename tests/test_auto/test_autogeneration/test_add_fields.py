import peewee as pw
import pytest

from miggy.auto import diff_one
from miggy.operations import MigrateOperation
from miggy.writer import OperationWriter
from tests.helpers import compare_dedent


class _M1(pw.Model):
    name = pw.CharField()

    class Meta:
        table_name = "some_name"


@pytest.mark.parametrize(
    ("test_field", "expected"),
    [
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """
            migrator.add_fields(
                'test',
                field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),
            )
            """,
            id="add_constraint",
        ),
        pytest.param(
            pw.IntegerField(default=5),
            """
            migrator.add_fields(
                'test',
                field=pw.IntegerField(default=5),
            )
            """,
            id="add_default",
        ),
        pytest.param(
            pw.IntegerField(default=lambda: 5),
            """
            migrator.add_fields(
                'test',
                field=pw.IntegerField(),
            )
            """,
            id="add_default_callable",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, on_delete="CASCADE", null=True),
            """
            migrator.add_fields(
                'test',
                field=pw.ForeignKeyField(model=migrator.state['_m1'], null=True, on_delete='CASCADE'),
            )
            """,
            id="add_fk",
        ),
    ],
)
def test_add_fields(test_field: pw.Field, expected: str) -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    class Test(pw.Model):
        first_name = pw.CharField()
        field = test_field

        class Meta:
            table_name = "test"

    operations = diff_one(Test, OldTest)
    assert len(operations) == 1
    assert isinstance(operations[0], MigrateOperation)
    compare_dedent(OperationWriter(operations[0]).serialize(), expected)
