import peewee as pw
import pytest

from miggy.auto import diff_one
from miggy.types import ModelCls
from tests.helpers import operation_to_one_line


@pytest.mark.parametrize(
    ("name_before", "name_after", "expected"),
    [
        (None, "new_name", ["migrator.rename_table('test','new_name',)"]),
        (None, "test", []),
        (None, None, []),
        ("new_name", None, ["migrator.rename_table('test','test',)"]),
    ],
)
def test_rename_table(name_before: str | None, name_after: str | None, expected: list[str]) -> None:
    def create_model(_table_name: str | None) -> ModelCls:
        class Test(pw.Model):
            i1 = pw.IntegerField()

            class Meta:
                table_name = _table_name

        return Test

    changes = diff_one(create_model(name_after), create_model(name_before))
    changes = [operation_to_one_line(c) for c in changes]  # type: ignore
    assert changes == expected
