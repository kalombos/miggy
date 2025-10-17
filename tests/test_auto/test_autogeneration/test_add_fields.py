import peewee as pw
import pytest

from peewee_migrate.auto import create_fields, diff_one
from peewee_migrate.migrator import Migrator
from peewee_migrate.types import Model


@pytest.mark.parametrize(
    ("test_field", "expected"),
    [
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")]),
            """field=pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])""",
            id="add_constraint",
        ),
        pytest.param(pw.IntegerField(default=5), """field=pw.IntegerField(default=5)""", id="add_default"),
        pytest.param(pw.IntegerField(default=lambda: 5), """field=pw.IntegerField()""", id="add_default_callable"),
        pytest.param(pw.IntegerField(null=True), """field=pw.IntegerField(null=True)""", id="add_nullable"),
    ],
)
def test_add_fields(sq_migrator: Migrator, test_field: pw.Field, expected: str) -> None:
    class OldTest(Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    class Test(Model):
        first_name = pw.CharField()
        field = test_field

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest, migrator=sq_migrator)[0]
    assert code == create_fields(Test, Test.field)
    assert expected in code
