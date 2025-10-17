import peewee as pw
import pytest

from peewee_migrate.auto import field_to_code, fields_not_equal


def test_field_to_code() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])

    assert field_to_code(SomeModel.name) == (
        """name = pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )


@pytest.mark.parametrize(
    ("f1", "f2", "expected"),
    [
        pytest.param(pw.IntegerField(), pw.IntegerField(), False, id="same"),
        pytest.param(pw.IntegerField(), pw.IntegerField(column_name="new_name"), True, id="column"),
        pytest.param(pw.IntegerField(index=True), pw.IntegerField(), True, id="index"),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 5")]), pw.IntegerField(), True, id="default_constraint"
        ),
        pytest.param(pw.IntegerField(default=5), pw.IntegerField(), True, id="default"),
        pytest.param(pw.IntegerField(default=lambda: 5), pw.IntegerField(), False, id="default_callable"),
        pytest.param(pw.IntegerField(), pw.IntegerField(unique=True), True, id="unique"),
        pytest.param(
            pw.IntegerField(index=False, unique=True),
            pw.IntegerField(index=True, unique=True),
            False,
            id="same indexes",
        ),
        pytest.param(pw.IntegerField(), pw.CharField(), True, id="type"),
        pytest.param(pw.CharField(max_length=5), pw.CharField(), True, id="max_length"),
    ],
)
def test_fields_not_equal(f1: pw.Field, f2: pw.Field, expected: bool) -> None:
    assert fields_not_equal(f1, f2) is expected
