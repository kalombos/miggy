import peewee as pw
import pytest

from peewee_migrate.auto import change_fields, diff_one
from peewee_migrate.migrator import Migrator
from peewee_migrate.types import Model


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
    ],
)
def test_change_fields(
    age_field_before: pw.Field, age_field_after: pw.Field, expected: str, sq_migrator: Migrator
) -> None:
    class OldTest(Model):
        first_name = pw.CharField()
        age = age_field_before

        class Meta:
            table_name = "test"

    class Test(Model):
        first_name = pw.CharField()
        age = age_field_after

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest, migrator=sq_migrator)[0]
    assert code == change_fields(Test, Test.age)
    assert expected in code
