import peewee as pw
import pytest

from peewee_migrate.auto import change_fields, create_fields, create_model, diff_many, diff_one
from peewee_migrate.migrator import Migrator
from peewee_migrate.types import Model


def test_create_model_w_constraint(sq_migrator: Migrator) -> None:
    class Test(Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

    code = diff_many([Test], [], migrator=sq_migrator)[0]
    assert code == create_model(Test)
    assert """first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")], max_length=255)""" in code


def test_add_field_w_constraint(sq_migrator: Migrator) -> None:
    class OldTest(Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

        class Meta:
            table_name = "test"

    class Test(Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        age = pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest, migrator=sq_migrator)[0]
    assert code == create_fields(Test, Test.age)
    assert """age=pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])""" in code


def test_drop_field_w_constraint(sq_migrator: Migrator) -> None:
    class OldTest(Model):
        first_name = pw.CharField()
        age = pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])

        class Meta:
            table_name = "test"

    class Test(Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest, migrator=sq_migrator)[0]
    assert code == "migrator.remove_fields('test', 'age')"


@pytest.mark.parametrize(
    ("age_field_before", "age_field_after", "expected"),
    [
        (
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """age=pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])""",
        ),
        (pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]), pw.IntegerField(), """age=pw.IntegerField()"""),
    ],
)
def test_change_field_constraint(
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
