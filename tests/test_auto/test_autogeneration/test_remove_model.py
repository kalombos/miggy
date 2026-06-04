import peewee as pw

from miggy.auto import MigrationAutodetector
from miggy.state import State
from tests.helpers import operation_to_one_line


def test_remove_model() -> None:
    class Test(pw.Model):
        constraint = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        i1 = pw.IntegerField()
        i2 = pw.IntegerField()

        class Meta:
            indexes = ((("i1", "i2"), True),)

    diffs = MigrationAutodetector(State({"test": Test}), State()).diff_many()
    changes = [operation_to_one_line(c) for c in diffs]
    assert changes == ["migrator.remove_model('test',)"]
