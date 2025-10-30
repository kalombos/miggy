import peewee as pw
import pytest

from peewee_migrate.auto import change_fields, diff_one
from peewee_migrate.utils import copy_model


class _M1(pw.Model):
    name = pw.CharField()


@pytest.mark.parametrize(
    ("age_field_before", "age_field_after", "expected"),
    [
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """age=pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])""",
            id="add_constraint",
        ),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            pw.IntegerField(),
            """age=pw.IntegerField()""",
            id="remove_constraint",
        ),
        pytest.param(
            pw.IntegerField(), pw.IntegerField(default=5), """age=pw.IntegerField(default=5)""", id="add_default"
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(default=lambda: 5, constraints=[pw.SQL("DEFAULT 5")]),
            """age=pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])""",
            id="default_callable",
        ),
        pytest.param(pw.IntegerField(default=5), pw.IntegerField(), """age=pw.IntegerField()""", id="remove_default"),
        pytest.param(
            pw.IntegerField(), pw.IntegerField(null=True), """age=pw.IntegerField(null=True)""", id="add_not_null"
        ),
        pytest.param(pw.IntegerField(null=True), pw.IntegerField(), """age=pw.IntegerField()""", id="remove_not_null"),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(column_name="new_name"),
            """age=pw.IntegerField(column_name='new_name')""",
            id="column_name",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.ForeignKeyField(_M1, column_name="new_name", on_update="RESTRICT"),
            (
                "age=pw.ForeignKeyField(backref='test_set', column_name='new_name', "
                "field='id', model=migrator.orm['_m1'], on_update='RESTRICT')"
            ),
            id="add_fk",
        ),
        pytest.param(
            pw.ForeignKeyField(_M1, column_name="new_name"),
            pw.IntegerField(),
            "age=pw.IntegerField()",
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

    class Test(pw.Model):
        first_name = pw.CharField()
        age = age_field_after

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest)[0]
    assert code == change_fields(Test, Test.age)
    assert expected in code


@pytest.mark.parametrize(
    ("field_before", "field_after"),
    [
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(_M1), id="fk_copy_model"),
        pytest.param(pw.ForeignKeyField(_M1), pw.ForeignKeyField(copy_model(_M1)), id="fk_copy_model"),
    ],
)
def test_change_field__no_changes(field_before: pw.Field, field_after: pw.Field) -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()
        age = field_before

    class Test(pw.Model):
        first_name = pw.CharField()
        age = field_after

    assert diff_one(Test, OldTest) == []
