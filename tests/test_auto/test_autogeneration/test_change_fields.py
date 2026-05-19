import peewee as pw
import pytest

from miggy.auto import diff_one
from miggy.utils import copy_model
from tests.helpers import operation_to_one_line, to_one_line


class _M1(pw.Model):
    name = pw.CharField()


@pytest.mark.parametrize(
    ("age_field_before", "age_field_after", "expected"),
    [
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """migrator.change_fields('test',age=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),)""",
            id="add_constraint",
        ),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            pw.IntegerField(),
            """migrator.change_fields('test',age=pw.IntegerField(),)""",
            id="remove_constraint",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=5),
            """migrator.change_fields('test',age=pw.IntegerField(default=5),)""",
            id="add_default",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=lambda: 5, constraints=[pw.SQL("DEFAULT 5")]),
            """migrator.change_fields('test',age=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),)""",
            id="default_callable",
        ),
        pytest.param(
            pw.IntegerField(default=5),
            pw.IntegerField(),
            """migrator.change_fields('test',age=pw.IntegerField(),)""",
            id="remove_default",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(null=True),
            """migrator.change_fields('test',age=pw.IntegerField(null=True),)""",
            id="add_not_null",
        ),
        pytest.param(
            pw.IntegerField(null=True),
            pw.IntegerField(),
            """migrator.change_fields('test',age=pw.IntegerField(),)""",
            id="remove_not_null",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(column_name="new_name"),
            """migrator.change_fields('test',age=pw.IntegerField(column_name='new_name'),)""",
            id="column_name",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.ForeignKeyField(_M1, column_name="new_name", on_update="RESTRICT", field="name"),
            (
                "migrator.change_fields('test',"
                "age=pw.ForeignKeyField("
                "column_name='new_name', "
                "field='name', "
                "model=migrator.state['_m1'], "
                "on_update='RESTRICT'),)"
            ),
            id="add_fk",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, column_name="new_name"),
            pw.IntegerField(),
            "migrator.change_fields('test',age=pw.IntegerField(),)",
            id="remove_fk",
        ),
    ],
)
def test_change_fields(age_field_before: pw.Field, age_field_after: pw.Field, expected: str) -> None:
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


@pytest.mark.parametrize(
    ("field_before", "field_after"),
    [
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1), id="fk_copy_model"),
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(copy_model(_M1)), id="fk_copy_model"),
    ],
)
def test_change_field__no_changes(field_before: pw.Field, field_after: pw.Field) -> None:
    def create_model(field: pw.Field):
        class Test(pw.Model):
            first_name = pw.CharField()
            age = field

        return Test

    assert diff_one(create_model(field_after), create_model(field_before)) == []
