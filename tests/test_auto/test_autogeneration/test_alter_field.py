import peewee as pw
import pytest

from miggy.auto import diff_one
from miggy.utils import copy_model
from miggy.writer import OperationWriter
from tests.helpers import compare_dedent, operation_to_one_line, to_one_line


class _M1(pw.Model):
    name = pw.CharField()


@pytest.mark.parametrize(
    ("age_field_before", "age_field_after", "expected"),
    [
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),)""",
            id="add_constraint",
        ),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            pw.IntegerField(),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(),)""",
            id="remove_constraint",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=5),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(default=5),)""",
            id="add_default",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=lambda: 5, constraints=[pw.SQL("DEFAULT 5")]),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),)""",
            id="default_callable",
        ),
        pytest.param(
            pw.IntegerField(default=5),
            pw.IntegerField(),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(),)""",
            id="remove_default",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(null=True),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(null=True),)""",
            id="add_not_null",
        ),
        pytest.param(
            pw.IntegerField(null=True),
            pw.IntegerField(),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(),)""",
            id="remove_not_null",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(column_name="new_name"),
            """migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(column_name='new_name'),)""",
            id="column_name",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.ForeignKeyField(_M1, column_name="new_name", on_update="RESTRICT", field="name"),
            (
                "migrator.alter_field(model_name='test',name='age',field=pw.ForeignKeyField("
                "column_name='new_name', "
                "field='name', "
                "model='_m1', "
                "on_update='RESTRICT'),)"
            ),
            id="add_fk",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, column_name="new_name"),
            pw.IntegerField(),
            "migrator.alter_field(model_name='test',name='age',field=pw.IntegerField(),)",
            id="remove_fk",
        ),
    ],
)
def test_alter_field(age_field_before: pw.Field, age_field_after: pw.Field, expected: str) -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()
        age = age_field_before

        class Meta:
            table_name = "test"

    OldTest._meta.add_field("age", age_field_before)

    class Test(pw.Model):
        first_name = pw.CharField()
        age = age_field_after

        class Meta:
            table_name = "test"

    Test._meta.add_field("age", age_field_after)

    changes = diff_one(Test, OldTest)
    changes = [operation_to_one_line(c) for c in changes]  # type: ignore
    assert changes == [to_one_line(expected)]


def test_alter_few_fields() -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()
        email = pw.CharField(null=True)
        last_name = pw.CharField(null=True)

        class Meta:
            table_name = "test"

    class Test(pw.Model):
        first_name = pw.CharField()
        email = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            table_name = "test"

    operations = diff_one(Test, OldTest)
    assert len(operations) == 2

    serialized = sorted([OperationWriter(o).serialize() for o in operations])
    compare_dedent(
        serialized[0], 
        """
        migrator.alter_field(
            model_name='test',
            name='email',
            field=pw.CharField(),
        )
        """
    )
    compare_dedent(
        serialized[1],
        """
        migrator.alter_field(
            model_name='test',
            name='last_name',
            field=pw.CharField(),
        )
        """
    )


@pytest.mark.parametrize(
    ("field_before", "field_after"),
    [
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1), id="fk_copy_model"),
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(copy_model(_M1)), id="fk_copy_model"),
    ],
)
def test_alter_field__no_changes(field_before: pw.Field, field_after: pw.Field) -> None:
    def create_model(field: pw.Field):
        class Test(pw.Model):
            first_name = pw.CharField()
            age = field

        return Test

    assert diff_one(create_model(field_after), create_model(field_before)) == []
