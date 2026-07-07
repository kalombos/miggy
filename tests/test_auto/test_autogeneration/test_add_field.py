import peewee as pw
import pytest

from miggy.operations import MigrateOperation
from miggy.writer import OperationWriter
from tests.helpers import compare_dedent, diff_one, get_active_status


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
            migrator.add_field(
                model_name='test',
                name='field',
                field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),
            )
            """,
            id="add_constraint",
        ),
        pytest.param(
            pw.IntegerField(default=5),
            """
            migrator.add_field(
                model_name='test',
                name='field',
                field=pw.IntegerField(default=5),
            )
            """,
            id="add_default",
        ),
        pytest.param(
            pw.CharField(default=get_active_status),
            """
            migrator.add_field(
                model_name='test',
                name='field',
                field=pw.CharField(default=tests.helpers.get_active_status),
            )
            """,
            id="add_default_callable",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, on_delete="CASCADE", null=True),
            """
            migrator.add_field(
                model_name='test',
                name='field',
                field=pw.ForeignKeyField(model='_m1', null=True, on_delete='CASCADE'),
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

    operations = diff_one(OldTest, Test)
    assert len(operations) == 1
    assert isinstance(operations[0], MigrateOperation)
    compare_dedent(OperationWriter(operations[0]).serialize(), expected)


def test_add_few_fields() -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    class Test(pw.Model):
        first_name = pw.CharField()
        email = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"

    operations = diff_one(OldTest, Test)
    assert len(operations) == 2
    serialized = sorted([OperationWriter(o).serialize() for o in operations])
    compare_dedent(
        serialized[0],
        """
        migrator.add_field(
            model_name='test',
            name='email',
            field=pw.CharField(),
        )
        """,
    )
    compare_dedent(
        serialized[1],
        """
        migrator.add_field(
            model_name='test',
            name='last_name',
            field=pw.CharField(),
        )
        """,
    )
